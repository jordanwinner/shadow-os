#!/usr/bin/env bash
# apercu.sh — montre le menu GRUB de Shadow sans redémarrer ni être root :
# une image GRUB EFI + le thème dans un dossier FAT, démarrés par QEMU (micrologiciel OVMF).
#
#   systeme/grub/apercu.sh [SORTIE.png]     (défaut : ./grub-apercu.png)
set -euo pipefail
ICI="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SORTIE="$(readlink -f "${1:-grub-apercu.png}")"
for o in grub-mkimage qemu-system-x86_64 python3 ffmpeg; do command -v "$o" >/dev/null || { echo "apercu : $o manquant" >&2; exit 1; }; done
OVMF=/usr/share/ovmf/OVMF.fd; [ -f "$OVMF" ] || { echo "apercu : $OVMF manquant (paquet ovmf)" >&2; exit 1; }

G="$(mktemp -d)"; trap 'kill "${Q:-0}" 2>/dev/null || true; rm -rf "$G"' EXIT
mkdir -p "$G/efi/EFI/BOOT" "$G/efi/boot/grub/themes"
cp -r "$ICI/shadow" "$G/efi/boot/grub/themes/shadow"
{
  echo 'insmod all_video'; echo 'insmod gfxterm'; echo 'insmod png'
  echo 'set gfxmode=1920x1080,auto'; echo 'terminal_output gfxterm'
  # une ligne par police, comme le fait update-grub (GRUB ne développe pas *.pf2 sans module)
  for f in "$G"/efi/boot/grub/themes/shadow/*.pf2; do echo "loadfont /boot/grub/themes/shadow/$(basename "$f")"; done
  echo 'set theme=/boot/grub/themes/shadow/theme.txt'; echo 'set timeout_style=menu'; echo 'set timeout=30'
  echo 'menuentry "Shadow" { true }'
  echo 'submenu "Options avancées pour Shadow" { menuentry "x" { true } }'
  echo 'menuentry "Paramètres du micrologiciel UEFI" { true }'
} > "$G/efi/boot/grub/grub.cfg"
grub-mkimage -O x86_64-efi -o "$G/efi/EFI/BOOT/BOOTX64.EFI" -p /boot/grub \
  part_gpt part_msdos fat normal configfile gfxterm gfxmenu all_video efi_gop png font echo test true loadenv
cp "$OVMF" "$G/OVMF.fd"
( cd "$G" && exec qemu-system-x86_64 -m 512 -bios OVMF.fd -drive format=raw,file=fat:rw:efi \
    -display none -vga std -monitor unix:mon.sock,server,nowait -net none ) >/dev/null 2>&1 &
Q=$!
sleep 22
python3 - "$G" <<'PY'
import socket, sys, time
g = sys.argv[1]
s = socket.socket(socket.AF_UNIX); s.connect(f'{g}/mon.sock'); time.sleep(0.3); s.recv(4096)
s.send(f'screendump {g}/grub.ppm\n'.encode()); time.sleep(1.5); s.send(b'quit\n'); time.sleep(0.5)
PY
ffmpeg -loglevel error -y -i "$G/grub.ppm" "$SORTIE"
echo "aperçu : $SORTIE"
