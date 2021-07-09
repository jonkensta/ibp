## ZeroPi Build Guide

### Platform </br>
The ZeroPi board designed by FriendlyELEC, uses an Allwinner SoC with ARM processor.

- Board: [ZeroPi](https://wiki.friendlyarm.com/wiki/index.php/ZeroPi) by FriendlyELEC
- SoC: Allwinner [H3](https://linux-sunxi.org/H3), "sunxi" series, [sun8i](https://linux-sunxi.org/Allwinner_SoC_Family) generation
- CPU: Cortex A7 by ARM, quad-core

----------------------------------------------------------------------------------------

### Summary </br>

Our platform uses an SD card containing three elements:
1. SPL and U-Boot: compiled together into a single binary
2. Linux root file system: obtained from ArchLinuxARM latest (contains uImage and dtbs)
3. The U-Boot script `boot.scr`, compiled from boot.cmd

----------------------------------------------------------------------------------------

### Quick Start </br>

```zsh

# setup U-Boot toolchain
pacman -S arm-none-eabi-gcc
pacman -S swig

# compile SPL and U-Boot
git clone https://source.denx.de/u-boot/u-boot.git
cd u-boot
make CROSS_COMPILE=arm-none-eabi- nanopi_neo_defconfig
make CROSS_COMPILE=arm-none-eabi- -j$(nproc)

# compile boot.scr (requires boot.cmd)
pacman -S uboot-tools
mkimage -A arm -O linux -T script -C none -a 0 -e 0 -n "ZeroPi Boot Script" -d boot.cmd boot.scr

# prep SD card
dd if=/dev/zero of=/dev/sdX bs=1M count=8
fdisk /dev/sdX
o, <enter> # create new label
n, <enter>, <enter>, <enter>, <enter>, <enter> # new partition, accept all defaults
w, <enter> # write changes and exit

# create filesystem and mount
mkfs.ext4 /dev/sdX1
mount /dev/sdX1 /mnt/<foo>

# download and extract Linux root file system
wget http://os.archlinuxarm.org/os/ArchLinuxARM-armv7-latest.tar.gz
bsdtar -xpf ArchLinuxARM-armv7-latest.tar.gz -C /mnt/<foo>
sync

# install bootloader and boot script
dd if=u-boot-sunxi-with-spl.bin of=/dev/sdX bs=1024 seek=8 
cp boot.scr /mnt/<foo>/boot/.
umount /mnt/<foo>

# done

```

----------------------------------------------------------------------------------------

## Detailed Walk-through </br>

### SPL and U-Boot </br>

```zsh

# install toolchain
% pacman -S arm-none-eabi-gcc

# clone U-Boot mainline repo
% git clone https://source.denx.de/u-boot/u-boot.git
Cloning into 'u-boot'...
remote: Enumerating objects: 783410, done.
remote: Counting objects: 100% (11019/11019), done.
remote: Compressing objects: 100% (4724/4724), done.
remote: Total 783410 (delta 7759), reused 8355 (delta 6230), pack-reused 772391
Receiving objects: 100% (783410/783410), 157.51 MiB | 8.07 MiB/s, done.
Resolving deltas: 100% (651893/651893), done.

# compilation steps

# cd to u-boot directory, remove any previously compiled files if needed
% make CROSS_COMPILE=arm-none-eabi- distclean

# apply board default configuration
% make CROSS_COMPILE=arm-none-eabi- nanopi_neo_defconfig
  HOSTCC  scripts/basic/fixdep
  HOSTCC  scripts/kconfig/conf.o
  YACC    scripts/kconfig/zconf.tab.c
  LEX     scripts/kconfig/zconf.lex.c
  HOSTCC  scripts/kconfig/zconf.tab.o
  HOSTLD  scripts/kconfig/conf

  configuration written to .config

# optional: run menuconfig to customize settings other than default config
% make CROSS_COMPILE=arm-none-eabi- menuconfig

# install the 'swig' package (required for compilation step)
sudo pacman -S swig

# compile
% make CROSS_COMPILE=arm-none-eabi- -j$(nproc)

# confirm the bootloader file 'u-boot-sunxi-with-spl.bin' was created:
% ls
api        disk      Kbuild       README      u-boot.cfg          u-boot.map
arch       doc       Kconfig      scripts     u-boot.cfg.configs  u-boot-nodtb.bin
board      drivers   lib          spl         u-boot.dtb          u-boot.srec
build      dts       Licenses     System.map  u-boot-dtb.bin      u-boot-sunxi-with-spl.bin
cmd        env       MAINTAINERS  test        u-boot-dtb.img      u-boot-sunxi-with-spl.map
common     examples  Makefile     tools       u-boot.dtb.out      u-boot.sym
config.mk  fs        net          u-boot      u-boot.img
configs    include   post         u-boot.bin  u-boot.lds

# note the bootloader location as we will write it to the SD card in a later step

```

----------------------------------------------------------------------------------------

### boot script </br>

U-Boot automatically looks for and execs `boot.scr` and `uEnv.txt`.
Our platform only uses `boot.scr`.

Create a file `boot.cmd` containing the source below (from the [Arch Wiki](https://wiki.archlinux.org/title/NanoPi_M1))

Note we added an additional U-Boot environment variable on line 3 for the ZeroPi:
`setenv fdtfile sun8i-h3-zeropi.dtb`

```zsh

part uuid ${devtype} ${devnum}:${bootpart} uuid
setenv bootargs console=${console} root=PARTUUID=${uuid} rw rootwait
setenv fdtfile sun8i-h3-zeropi.dtb

if load ${devtype} ${devnum}:${bootpart} ${kernel_addr_r} /boot/zImage; then
  if load ${devtype} ${devnum}:${bootpart} ${fdt_addr_r} /boot/dtbs/${fdtfile}; then
    if load ${devtype} ${devnum}:${bootpart} ${ramdisk_addr_r} /boot/initramfs-linux.img; then
      bootz ${kernel_addr_r} ${ramdisk_addr_r}:${filesize} ${fdt_addr_r};
    else
      bootz ${kernel_addr_r} - ${fdt_addr_r};
    fi;
  fi;
fi

if load ${devtype} ${devnum}:${bootpart} 0x48000000 /boot/uImage; then
  if load ${devtype} ${devnum}:${bootpart} 0x43000000 /boot/script.bin; then
    setenv bootm_boot_mode sec;
    bootm 0x48000000;
  fi;
fi

```

Compile `boot.scr` from `boot.cmd` using `mkimage` in the `uboot-tools` package.

```zsh
# install uboot-tools
% sudo pacman -S uboot-tools

# compile our boot script 'boot.scr'
% mkimage -A arm -O linux -T script -C none -a 0 -e 0 -n "ZeroPi Boot Script" -d boot.cmd boot.scr

# note the boot script location as we will write it to the SD card in a later step

```

----------------------------------------------------------------------------------------

### SD Card </br>

We use a SanDisk 16GB micro (Class 10) SD card.

Note this process completely rewrites the SD card; all existing data will be lost.

```zsh

# confirm SD card name 'sdX', for example, 'sdc' below
% lsblk
NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
sda           8:0    1     0B  0 disk 
sdb           8:16   1     0B  0 disk 
sdc           8:32   1  14.8G  0 disk 
nvme0n1     259:0    0 465.8G  0 disk 
├─nvme0n1p1 259:1    0   512M  0 part /boot
├─nvme0n1p2 259:2    0     8G  0 part [SWAP]
└─nvme0n1p3 259:3    0 457.3G  0 part /

# write zeros to the beginning of the card (replace 'sdX' with your SD card name)
% sudo dd if=/dev/zero of=/dev/sdX bs=1M count=8
[sudo] password for root: 
8+0 records in
8+0 records out
8388608 bytes (8.4 MB, 8.0 MiB) copied, 3.1184 s, 2.7 MB/s

# use fdisk to partition the rest of the card
% sudo fdisk /dev/sdX
[sudo] password for root: 

Welcome to fdisk (util-linux 2.37).
Changes will remain in memory only, until you decide to write them.
Be careful before using the write command.
Command (m for help): 

# create a new empty DOS partition table
Command (m for help): o
Created a new DOS disklabel with disk identifier 0xe1cbda54.

# verify all previous partitions were removed
Command (m for help): p
Disk /dev/sdc: 14.84 GiB, 15931539456 bytes, 31116288 sectors
Disk model: CardReader SD2  
Units: sectors of 1 * 512 = 512 bytes
Sector size (logical/physical): 512 bytes / 512 bytes
I/O size (minimum/optimal): 512 bytes / 512 bytes
Disklabel type: dos
Disk identifier: 0xe1cbda54

# create a new primary partition, save changes and exit
Command (m for help): n
Partition type
   p   primary (0 primary, 0 extended, 4 free)
   e   extended (container for logical partitions)
Select (default p): p
Partition number (1-4, default 1): 1
First sector (2048-31116287, default 2048): 2048
Last sector, +/-sectors or +/-size{K,M,G,T,P} (2048-31116287, default 31116287): 

Created a new partition 1 of type 'Linux' and of size 14.8 GiB.

Command (m for help): w
The partition table has been altered.
Calling ioctl() to re-read partition table.
Syncing disks.

# verify the new partition 'sdX1', for example 'sdc1' below:
% lsblk
NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
sda           8:0    1     0B  0 disk 
sdb           8:16   1     0B  0 disk 
sdc           8:32   1  14.8G  0 disk 
└─sdc1        8:33   1  14.8G  0 part 
nvme0n1     259:0    0 465.8G  0 disk 
├─nvme0n1p1 259:1    0   512M  0 part /boot
├─nvme0n1p2 259:2    0     8G  0 part [SWAP]
└─nvme0n1p3 259:3    0 457.3G  0 part /

# create the ext4 filesystem on sdX1 (not sdX), this will take a minute or so
% sudo mkfs.ext4 /dev/sdX1
[sudo] password for root: 
mke2fs 1.46.2 (28-Feb-2021)
Creating filesystem with 3889280 4k blocks and 972944 inodes
Filesystem UUID: 113314f0-b772-40ec-869e-8f5ddd9305ab
Superblock backups stored on blocks: 
	32768, 98304, 163840, 229376, 294912, 819200, 884736, 1605632, 2654208

Allocating group tables: done                            
Writing inode tables: done                            
Creating journal (16384 blocks): done
Writing superblocks and filesystem accounting information: done  

# mount the file system to /mnt/<foo>
% sudo mount /dev/sdX1 /mnt/zeropi/mnt

# verify
% lsblk
NAME        MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
sda           8:0    1     0B  0 disk 
sdb           8:16   1     0B  0 disk 
sdc           8:32   1  14.8G  0 disk 
└─sdc1        8:33   1  14.8G  0 part /mnt/zeropi/mnt
nvme0n1     259:0    0 465.8G  0 disk 
├─nvme0n1p1 259:1    0   512M  0 part /boot
├─nvme0n1p2 259:2    0     8G  0 part [SWAP]
└─nvme0n1p3 259:3    0 457.3G  0 part /

# download and extract the root file system
% wget http://os.archlinuxarm.org/os/ArchLinuxARM-armv7-latest.tar.gz

# uncompress and write to the mount point /mnt/<foo>
# NOTE the '-C' flag to specify destination directory
% sudo bsdtar -xpf ArchLinuxARM-armv7-latest.tar.gz -C /mnt/zeropi/mnt 

# write the changes (this may take a couple of minutes)
% sync

# install the U-Boot bootloader
% sudo dd if=u-boot-sunxi-with-spl.bin of=/dev/sdX bs=1024 seek=8 

# copy the boot script to the mount point /mnt/<foo>/boot 
% sudo cp boot.scr /mnt/zeropi/mnt/boot/.

# unmount the SD card mount point /mnt/<foo>
% sudo umount /mnt/zeropi/mnt

# now, behold the stupendous glory of U-Boot and Arch Linux on the ZeroPi

```

----------------------------------------------------------------------------------------

### Boot Process Details </br>

There are 4 steps to the boot process:</br>

```
RBL → SPL → U-Boot → Linux
```

1. RBL (ROM bootloader): runs from ROM of the SoC when board is powered on
   - sets up stack, watchdog timer, system clock (using PLL)
   - searches memory devices for SPL image (in our case, first partition of SD card)
   - copies SPL from external memory device (SD card) to internal SRAM (SoC)
   - executes SPL

2. SPL (Secondary Program Loader, or MLO/Memory Loader): runs from internal SRAM (SoC)
   - inits UART console for debug messages
   - reconfigures PLL, inits DDR memory, configs boot peripherals (pin muxing)
   - searches memory devices for U-Boot image (in our case, first partition of SD card)
   - copies U-Boot image from external memory device (SD card) into DDR memory
   - passes control to U-Boot

3. U-Boot: runs from DDR memory
   - inits relevant peripherals to support loading the kernel
   - runs script to set destinations (DDR memory addresses) for Linux kernel and DTBs
   - loads Linux kernel image `/boot/zImage` and DTB/FDT `/boot/dtbs` from the
     SD card to the preset destinations in DDR memory
   - passes arguments (console settings, location of Linux RFS on SD card, and memory
     addresses of Linux kernel and the DTB/FDT in DDR memory) and transfers control to
     the Linux bootstrap loader 

4. Linux bootstrap loader: runs from DDR memory
   - uses the arguments and memory locations received from U-Boot to locate, decompress,
     nconfig, and init the Linux kernel.

----------------------------------------------------------------------------------------

### Boot Component Details </br>

**RBL:** </br>
The RBL is created by the vendor, placed in the ROM and executes automatically. It has
a few simple but critical functions including the task to find and execute the SPL. We
don't need to modify this component and it's also not possible to modify it.

**SPL:** </br>
We use the U-Boot mainline repository to create the SPL as well as the full U-Boot
bootloader. Some platforms separate these elements into the MLO (SPL) and full U-Boot
but on our platform they are compiled together into a single image.

U-Boot buckets common software architecture elements by CPU, SoC, and Board. For
example, all boards using an Arm Cortex A7 CPU (such as our ZeroPi), will use the same
CPU initialization code for compilation. Similarly, all boards using an AllWinner H3
SoC will use the same SoC initialization source code.

- CPU: `u-boot/arch/arm/cpu/armv7/sunxi`
- SoC: `u-boot/arch/arm/mach-sunxi`

The SPL functionality (by design) is not as complex as the full U-Boot bootloader. The
SPL only needs to know about the CPU and some of the SoC peripherals so it can
initialize these aspects and hand off control to the full U-Boot.

RBL → [ start.S → CPU inits → SoC inits ] → full U-Boot

**U-Boot:** </br>
Board inits occur during the full U-Boot process. All `sunxi` boards use the same
source for common initialization settings but the ZeroPi does not have a specific
Default Configuration. This is not unusual; multiple boards from a particular vendor
will often share the same components and thus the same configuration settings. We use
the `NanoPi Neo` defconfig as it is very similar to the `ZeroPi`.

- Board: `u-boot/board/sunxi`
- Default Configuration: `u-boot/configs/nanopi_neo_defconfig`

NOTE: additional customization of the Default Configuration is possible during the
compilation steps using the CLI-based `menuconfig` tool included with U-Boot.
 
**Linux:** </br>

This board is fully supported by mainline Linux (linux/arch/arm/mach-sunxi)

//TODO - add a note here about the CPU, SoC, Board, and DTB sources in Linux

----------------------------------------------------------------------------------------

### Serial Console </br>

**Serial Cable** </br>
We use a USB to TTL Serial Cable from [Adafruit](https://www.adafruit.com/product/954).

**Wiring Guide** </br>

| NanoPi (pin) | NanoPi (signal) | USB to Serial |
|:------------:|:---------------:|:-------------:|
|      1       |    GND          |     black     |
|      2       |    VDD 5V       |     red       |
|      3       |    UART TXD0    |     white     |
|      4       |    UART RXD0    |     green     |


**Console Setup** </br>

```zsh
# use dmesg to verify the tty for your device
% sudo dmesg -T --follow

# for example, ttyUSB0
usb 1-3.2: new full-speed USB device number 7 using xhci_hcd
usb 1-3.2: New USB device found, idVendor=10c4, idProduct=ea60, bcdDevice= 1.00
usb 1-3.2: New USB device strings: Mfr=1, Product=2, SerialNumber=3
usb 1-3.2: Product: CP2102 USB to UART Bridge Controller
usb 1-3.2: Manufacturer: Silicon Labs
usb 1-3.2: SerialNumber: 0001
cp210x 1-3.2:1.0: cp210x converter detected
usb 1-3.2: cp210x converter now attached to ttyUSB0

# if dmesg lists a new USB device but there is no message about tty attached,
# reboot your host machine with the USB serial cable attached and check again

# install and use picocom to connect to the ZeroPi via /dev/<ttyUSB>
% sudo pacman -S picocom
% picocom --baud 115200 /dev/ttyUSB0
picocom v3.1

port is        : /dev/ttyUSB0
flowcontrol    : none
baudrate is    : 115200
parity is      : none
databits are   : 8
stopbits are   : 1
escape is      : C-a
local echo is  : no
noinit is      : no
noreset is     : no
hangup is      : no
nolock is      : no
send_cmd is    : sz -vv
receive_cmd is : rz -vv -E
imap is        : 
omap is        : 
emap is        : crcrlf,delbs,
logfile is     : none
initstring     : none
exit_after is  : not set
exit is        : no

Type [C-a] [C-h] to see available commands
Terminal ready

# if the ZeroPi is already booted up, hit <enter> and you should see the login prompt.

alarm login: 

```

----------------------------------------------------------------------------------------

### OS Setup </br>

```zsh
# verify ethernet is up and has an ip address
% ping -c 3 1.1.1.1
PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=58 time=19.4 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=58 time=29.1 ms
64 bytes from 1.1.1.1: icmp_seq=3 ttl=58 time=19.3 ms

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 19.338/22.629/29.124/4.592 ms

% ip addr 
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc mq state UP group default qlen 1000
    link/ether ea:bf:68:23:7d:dd brd ff:ff:ff:ff:ff:ff
    inet 192.168.1.32/24 brd 192.168.1.255 scope global dynamic eth0
       valid_lft 85938sec preferred_lft 85938sec
    inet6 fe80::e8bf:68ff:fe23:7ddd/64 scope link 
       valid_lft forever preferred_lft forever

# init the pacman keyring
% pacman-key --init
% pacman-key --populate archlinuxarm

# install vim, bash-completion
% pacman -S vim bash-completion

# setup hostname, for example a server named "foo"
% echo foo > /etc/hostname

# setup hosts
% vim /etc/hosts

127.0.0.1   localhost
::1         localhost
127.0.1.1   <myhostname>.localdomain    <myhostname>

# setup language
% echo LANG=en_US.UTF-8 > /etc/locale.conf
% export LANG=en_US.UTF-8

# setup locale
% vim /etc/locale.gen # uncomment your locale ('en_US.UTF-8')
% locale-gen # generate the new locale
% locale # show current locale

# setup timezone
% timedatectl set-timezone US/Central
% ln -sf /usr/share/zoneinfo/US/Central /etc/localtime

# setup ntp
pacman -S ntp
systemctl enable ntpd.service
systemctl start ntpd.service
timedatectl set-ntp true

# setup hardware clock
hwclock --systohc --utc  # generates /etc/adjtime

# verify
timedatectl
date
hwclock --verbose

# enable trim for SSDs (weekly timer)
systemctl enable fstrim.timer  # inactive until reboot

# add TERM export line to bottom of /etc/profile
% export TERM=xterm-256color

# add ibp user and set password
% useradd -m ibp
% passwd ibp

# reboot and check for boot errors (as root)
% journalctl -b

# delete alarm user (after reboot)
% userdel alarm

# don't forget to change the root password!

```

----------------------------------------------------------------------------------------
