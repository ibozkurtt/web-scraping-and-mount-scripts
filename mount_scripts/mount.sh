#!/bin/bash

# Check if SSD is mounted
if mount | grep -qs '/mnt/ssd'; then
    echo "/mnt/ssd is already mounted."
else
    /bin/mount -t exfat UUID=65B3-7336 /mnt/ssd -o uid=1000,gid=1000,umask=000
fi

# Check if NVMe is mounted
if mount | grep -qs '/mnt/NVMe'; then
    echo "/mnt/NVMe is already mounted."
else
    /bin/mount -t vfat -o rw,uid=1000,gid=1000,umask=000 UUID=0F26-3E14 /mnt/NVMe
fi
