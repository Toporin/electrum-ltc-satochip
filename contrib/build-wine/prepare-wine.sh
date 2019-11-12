#!/bin/bash

# Please update these carefully, some versions won't work under Wine
NSIS_FILENAME=nsis-3.04-setup.exe
NSIS_URL=https://prdownloads.sourceforge.net/nsis/$NSIS_FILENAME?download
NSIS_SHA256=4e1db5a7400e348b1b46a4a11b6d9557fd84368e4ad3d4bc4c1be636c89638aa

ZBAR_FILENAME=zbarw-20121031-setup.exe
ZBAR_URL=https://sourceforge.net/projects/zbarw/files/$ZBAR_FILENAME/download
ZBAR_SHA256=177e32b272fa76528a3af486b74e9cb356707be1c5ace4ed3fcee9723e2c2c02

LIBUSB_FILENAME=libusb-1.0.22.7z
LIBUSB_URL=https://prdownloads.sourceforge.net/project/libusb/libusb-1.0/libusb-1.0.22/$LIBUSB_FILENAME?download
LIBUSB_SHA256=671f1a420757b4480e7fadc8313d6fb3cbb75ca00934c417c1efa6e77fb8779b

PYINSTALLER_REPO="https://github.com/SomberNight/pyinstaller.git"
PYINSTALLER_COMMIT=46fc8155710631f84ebe20e32e0a6ba6df76d366
# ^ tag 3.5, plus a custom commit that fixes cross-compilation with MinGW

#Satochip pyscard
#PYSCARD_FILENAME=pyscard-1.9.7-cp36-cp36m-win_amd64.whl #python64-bits
#PYSCARD_URL=https://sourceforge.net/projects/pyscard/files/pyscard/pyscard%201.9.7/pyscard-1.9.7-cp36-cp36m-win_amd64.whl/download
#PYSCARD_SHA256=c63a87e4e7c87ce4c1299a1d8e0cae4e43f27451ca210f2c54f2dcd7467565c5
# PYSCARD_FILENAME=pyscard-1.9.8-cp36-cp36m-win32.whl #python32-bits
# PYSCARD_URL=https://ci.appveyor.com/api/buildjobs/j60tkykj6vh0ppiy/artifacts/dist%2Fpyscard-1.9.8-cp36-cp36m-win32.whl
# PYSCARD_SHA256=4641b5db53fb3562671b7b7c685ddf8f715180e2809106fb2a9361dfad553b4b
PYSCARD_FILENAME=pyscard-1.9.9-cp36-cp36m-win32.whl  # python 3.6, 32-bit
PYSCARD_URL=https://ci.appveyor.com/api/buildjobs/3uiua5o4llvpegbp/artifacts/dist/pyscard-1.9.9-cp36-cp36m-win32.whl
PYSCARD_SHA256=99d2b450f322f9ed9682fd2a99d95ce781527e371006cded38327efca8158fe7


PYTHON_VERSION=3.6.8

## These settings probably don't need change
export WINEPREFIX=/opt/wine64
export WINEDEBUG=-all

PYTHON_FOLDER="python3"
PYHOME="c:/$PYTHON_FOLDER"
PYTHON="wine $PYHOME/python.exe -OO -B"


# Let's begin!
set -e

here="$(dirname "$(readlink -e "$0")")"

. "$CONTRIB"/build_tools_util.sh

info "Booting wine."
wine 'wineboot'


cd "$CACHEDIR"

info "Installing Python."
# note: you might need "sudo apt-get install dirmngr" for the following
# keys from https://www.python.org/downloads/#pubkeys
KEYRING_PYTHON_DEV="keyring-electrum-build-python-dev.gpg"
gpg --no-default-keyring --keyring $KEYRING_PYTHON_DEV --import "$here"/gpg_keys/7ED10B6531D7C8E1BC296021FC624643487034E5.asc
PYTHON_DOWNLOADS="$CACHEDIR/python$PYTHON_VERSION"
mkdir -p "$PYTHON_DOWNLOADS"
for msifile in core dev exe lib pip tools; do
    echo "Installing $msifile..."
    download_if_not_exist "$PYTHON_DOWNLOADS/${msifile}.msi" "https://www.python.org/ftp/python/$PYTHON_VERSION/win32/${msifile}.msi"
    download_if_not_exist "$PYTHON_DOWNLOADS/${msifile}.msi.asc" "https://www.python.org/ftp/python/$PYTHON_VERSION/win32/${msifile}.msi.asc"
    verify_signature "$PYTHON_DOWNLOADS/${msifile}.msi.asc" $KEYRING_PYTHON_DEV
    wine msiexec /i "$PYTHON_DOWNLOADS/${msifile}.msi" /qb TARGETDIR=$PYHOME
done

info "Installing build dependencies."
$PYTHON -m pip install --no-warn-script-location -r "$CONTRIB"/deterministic-build/requirements-wine-build.txt

info "Installing dependencies specific to binaries."
$PYTHON -m pip install --no-warn-script-location -r "$CONTRIB"/deterministic-build/requirements-binaries.txt

info "Installing ZBar."
download_if_not_exist "$CACHEDIR/$ZBAR_FILENAME" "$ZBAR_URL"
verify_hash "$CACHEDIR/$ZBAR_FILENAME" "$ZBAR_SHA256"
wine "$CACHEDIR/$ZBAR_FILENAME" /S

#Satochip install pyscard
info "Installing pyscard..."
download_if_not_exist $PYSCARD_FILENAME "$PYSCARD_URL"
verify_hash $PYSCARD_FILENAME "$PYSCARD_SHA256"
$PYTHON -m pip install "$CACHEDIR/$PYSCARD_FILENAME"

info "Installing NSIS."
download_if_not_exist "$CACHEDIR/$NSIS_FILENAME" "$NSIS_URL"
verify_hash "$CACHEDIR/$NSIS_FILENAME" "$NSIS_SHA256"
wine "$CACHEDIR/$NSIS_FILENAME" /S

info "Installing libusb."
download_if_not_exist "$CACHEDIR/$LIBUSB_FILENAME" "$LIBUSB_URL"
verify_hash "$CACHEDIR/$LIBUSB_FILENAME" "$LIBUSB_SHA256"
7z x -olibusb "$CACHEDIR/$LIBUSB_FILENAME" -aoa
cp libusb/MS32/dll/libusb-1.0.dll $WINEPREFIX/drive_c/$PYTHON_FOLDER/

mkdir -p $WINEPREFIX/drive_c/tmp
cp "$CACHEDIR/secp256k1/libsecp256k1.dll" $WINEPREFIX/drive_c/tmp/


info "Building PyInstaller."
# we build our own PyInstaller boot loader as the default one has high
# anti-virus false positives
(
    cd "$WINEPREFIX/drive_c/electrum-ltc"
    ELECTRUM_COMMIT_HASH=$(git rev-parse HEAD)
    cd "$CACHEDIR"
    rm -rf pyinstaller
    mkdir pyinstaller
    cd pyinstaller
    # Shallow clone
    git init
    git remote add origin $PYINSTALLER_REPO
    git fetch --depth 1 origin $PYINSTALLER_COMMIT
    git checkout FETCH_HEAD
    rm -fv PyInstaller/bootloader/Windows-*/run*.exe || true
    # add reproducible randomness. this ensures we build a different bootloader for each commit.
    # if we built the same one for all releases, that might also get anti-virus false positives
    echo "const char *electrum_tag = \"tagged by Electrum@$ELECTRUM_COMMIT_HASH\";" >> ./bootloader/src/pyi_main.c
    pushd bootloader
    # cross-compile to Windows using host python
    python3 ./waf all CC=i686-w64-mingw32-gcc CFLAGS="-Wno-stringop-overflow -static"
    popd
    # sanity check bootloader is there:
    [[ -e PyInstaller/bootloader/Windows-32bit/runw.exe ]] || fail "Could not find runw.exe in target dir!"
) || fail "PyInstaller build failed"
info "Installing PyInstaller."
$PYTHON -m pip install --no-dependencies --no-warn-script-location ./pyinstaller

info "Wine is configured."
