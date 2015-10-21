#!/bin/sh

# Find any JPG or PNG images and strip all metadata from them, overwriting original image

if ! type exiftool > /dev/null; then
    echo "exiftool is not installed, try: apt-get install libimage-exiftool-perl"
    exit
fi

find . -type f \( -iname *.png -o -iname *.jpg \) | xargs exiftool -all= -overwrite_original
