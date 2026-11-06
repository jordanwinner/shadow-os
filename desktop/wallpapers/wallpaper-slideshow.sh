#!/bin/bash
WALLPAPER_DIR="/home/jordan/Images/Wallpapers"
INTERVAL=60

while true; do
    find "$WALLPAPER_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" \) | shuf | while read img; do
        gsettings set org.gnome.desktop.background picture-uri "file://$img"
        gsettings set org.gnome.desktop.background picture-uri-dark "file://$img"
        sleep "$INTERVAL"
    done
done
