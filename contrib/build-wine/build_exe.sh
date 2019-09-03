#!/bin/bash

FRESH_CLONE=contrib/build-wine/fresh_clone && \
    sudo rm -rf $FRESH_CLONE && \
    mkdir -p $FRESH_CLONE && \
    cd $FRESH_CLONE  && \
    git clone https://github.com/Toporin/electrum-ltc-satochip.git && \
    cd electrum-ltc-satochip
     
#git checkout $REV
sudo docker run -it \
    --name electrum-ltc-wine-builder-cont \
    -v $PWD:/opt/wine64/drive_c/electrum-ltc \
    --rm \
    --workdir /opt/wine64/drive_c/electrum-ltc/contrib/build-wine \
    electrum-ltc-wine-builder-img \
    ./build.sh
