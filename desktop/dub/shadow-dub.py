#!/usr/bin/env python3
"""
shadow-dub — traducteur audio en temps réel.
Capture le son qui SORT de l'ordinateur (un film, une vidéo…), le transcrit,
le traduit, puis :
  - affiche des sous-titres (terminal + fichier lu par l'îlot) ;
  - et/ou re-synthétise la voix dans la langue cible (doublage, option --mode dub).

usage : shadow-dub.py --from en --to fr [--mode sub|dub|both] [--model tiny|base|small]
Dépendances : faster-whisper, piper-tts (doublage), translate-shell (trans), pipewire.
Rien n'est envoyé nulle part sauf la traduction texte (translate-shell → en ligne).
"""
import sys, os, argparse, subprocess, shutil, time, json, re

SUB_FILE = os.path.expanduser("~/.local/share/shadow-desktop/subtitle.json")
PID_FILE = os.path.expanduser("~/.local/share/shadow-desktop/dub.pid")

# voix piper par langue cible (pour le doublage). Télécharge avec :
#   python3 -m piper.download_voices <nom>
# Si la voix manque, le doublage se rabat sur les sous-titres (qui, eux,
# marchent pour TOUTES les langues que Whisper + translate-shell gèrent).
PIPER_VOICE = {
    "fr": "fr_FR-siwis-medium",
    "en": "en_US-lessac-medium",
    "es": "es_ES-davefx-medium",
    "de": "de_DE-thorsten-medium",
    "it": "it_IT-paola-medium",
    "pt": "pt_BR-faber-medium",
    "nl": "nl_NL-mls-medium",
    "ru": "ru_RU-dmitri-medium",
    "pl": "pl_PL-darkman-medium",
    "zh": "zh_CN-huayan-medium",
    "uk": "uk_UA-ukrainian_tts-medium",
    "tr": "tr_TR-dfki-medium",
    "ar": "ar_JO-kareem-medium",
    "ca": "ca_ES-upc_ona-medium",
}

# quelques codes diffèrent entre Whisper et translate-shell
TRANS_CODE = {"zh": "zh-CN", "pt": "pt-BR"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def default_monitor():
    """Nom de la source 'monitor' du haut-parleur par défaut (ce qu'on entend)."""
    try:
        out = subprocess.run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"],
                             capture_output=True, text=True, timeout=5).stdout
        m = re.search(r'node\.name\s*=\s*"([^"]+)"', out)
        if m:
            return m.group(1) + ".monitor"
    except Exception:
        pass
    return None


def write_subtitle(src_text, tr_text, src, tgt):
    try:
        tmp = SUB_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"src": src_text, "tr": tr_text, "from": src, "to": tgt,
                       "ts": time.time()}, f)
        os.replace(tmp, SUB_FILE)
    except Exception:
        pass


def translate(text, src, tgt):
    if not text:
        return ""
    t = TRANS_CODE.get(tgt, tgt)
    s = TRANS_CODE.get(src, src)
    pair = f":{t}" if src == "auto" else f"{s}:{t}"   # ":fr" = détection auto → fr
    try:
        r = subprocess.run(["trans", "-b", "-no-autocorrect", pair, text],
                           capture_output=True, text=True, timeout=15)
        out = r.stdout.strip()
        return out or text
    except Exception:
        return text


class Dubber:
    def __init__(self, tgt):
        import glob
        self.tgt = tgt
        self.voice = PIPER_VOICE.get(tgt)
        self.model = None
        if self.voice:
            fn = self.voice + ".onnx"
            # dossiers dédiés : recherche récursive (petits) ; sinon non-récursif
            deep = [os.path.expanduser("~/.local/share/shadow-desktop/dub/voices"),
                    os.path.expanduser("~/.local/share/piper"),
                    os.path.expanduser("~/.local/share/piper-voices"),
                    os.path.expanduser("~/.cache/piper")]
            flat = [os.getcwd(), os.path.expanduser("~")]
            for d in deep:
                hits = glob.glob(os.path.join(d, "**", fn), recursive=True)
                if hits:
                    self.model = hits[0]
                    break
            if not self.model:
                for d in flat:
                    p = os.path.join(d, fn)
                    if os.path.exists(p):
                        self.model = p
                        break
        self.piper = shutil.which("piper") or os.path.expanduser("~/.local/bin/piper")
        self.player = shutil.which("pw-play") or shutil.which("paplay") or shutil.which("aplay")
        self.ok = bool(self.model) and os.path.exists(self.piper) and bool(self.player)

    def say(self, text):
        if not self.ok or not text:
            return
        try:
            wav = "/tmp/shadow-dub-tts.wav"
            p = subprocess.run([self.piper, "-m", self.model, "-f", wav],
                               input=text, text=True, capture_output=True, timeout=30)
            if p.returncode == 0 and os.path.exists(wav):
                subprocess.run([self.player, wav], capture_output=True, timeout=30)
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default="en")
    ap.add_argument("--to", dest="tgt", default="fr")
    ap.add_argument("--mode", choices=["sub", "dub", "both"], default="sub")
    ap.add_argument("--model", default="base")
    ap.add_argument("--window", type=float, default=5.0, help="secondes par tranche")
    args = ap.parse_args()

    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except Exception as e:
        log("Dépendance manquante :", e)
        log("Installe :  pip install --user faster-whisper")
        sys.exit(1)

    mon = default_monitor()
    if not mon:
        log("Impossible de trouver la sortie audio (monitor). PipeWire tourne ?")
        sys.exit(1)

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    log(f"▸ Modèle Whisper « {args.model} » (chargement…)")
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    dubber = Dubber(args.tgt) if args.mode in ("dub", "both") else None
    if args.mode in ("dub", "both") and (not dubber or not dubber.ok):
        log("⚠ doublage indisponible (piper/voix manquant) → sous-titres seulement")

    rate = 16000
    rec = subprocess.Popen(
        ["pw-record", "--target", mon, "--rate", str(rate), "--channels", "1",
         "--format", "s16", "-"],
        stdout=subprocess.PIPE)
    log(f"▸ Écoute du son système ({mon})")
    log(f"▸ {args.src} → {args.tgt} · mode {args.mode} · Ctrl+C pour arrêter\n")

    # Segmentation par les silences : on transcrit un énoncé COMPLET dès qu'une
    # pause est détectée (plutôt que de couper toutes les N secondes au milieu des
    # mots). Une borne max garde la latence raisonnable si ça parle sans arrêt.
    lang = None if args.src == "auto" else args.src
    MIN_SEG = int(rate * 1.8)                 # au moins ~1.8 s avant de transcrire
    MAX_SEG = int(rate * max(5.0, args.window))  # borne de latence
    SIL_WIN = int(rate * 0.6)                 # fenêtre d'analyse du silence
    sil_thresh = 0.010                        # seuil RMS (auto-ajusté au bruit de fond)
    noise = 0.004
    buf = np.zeros(0, np.float32)
    prev = ""
    try:
        while True:
            data = rec.stdout.read(4096)
            if not data:
                break
            buf = np.concatenate([buf, np.frombuffer(data, np.int16).astype(np.float32) / 32768.0])
            if len(buf) < MIN_SEG:
                continue
            tail = buf[-SIL_WIN:]
            rms = float(np.sqrt(np.mean(tail * tail)))
            # suit le niveau de fond pour s'adapter (musique douce, ambiance…)
            noise = 0.98 * noise + 0.02 * rms
            is_pause = rms < max(sil_thresh, noise * 1.6)
            if not (is_pause or len(buf) >= MAX_SEG):
                continue
            seg = buf
            buf = np.zeros(0, np.float32)
            if float(np.sqrt(np.mean(seg * seg))) < 0.006:   # quasi silence → rien à dire
                continue
            segs, _ = model.transcribe(seg, language=lang, vad_filter=True,
                                       beam_size=1, no_speech_threshold=0.5)
            text = re.sub(r"\s+", " ", " ".join(s.text for s in segs).strip())
            if not text or len(text) < 2:
                continue
            if text == prev or (prev and (text in prev or prev.endswith(text))):
                continue
            prev = text
            tr = translate(text, args.src, args.tgt)
            write_subtitle(text, tr, args.src, args.tgt)
            print(f"\033[90m{args.src}:\033[0m {text}")
            print(f"\033[36m{args.tgt}:\033[0m {tr}\n", flush=True)
            if dubber and dubber.ok:
                dubber.say(tr)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            rec.terminate()
        except Exception:
            pass
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
        log("\n▸ Arrêté.")


if __name__ == "__main__":
    main()
