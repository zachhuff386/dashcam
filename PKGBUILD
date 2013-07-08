# Maintainer: Zachary Huff <zach.huff.386@gmail.com>

pkgname=dashcam
pkgver=0.1.0
pkgrel=2
pkgdesc="C/Python dashcam built with Gstreamer for Raspberry Pi/BeagleBone Black"
arch=("any")
license=("GPL3")
url="https://github.com/zachhuff386/${pkgname}"
depends=(
    "python2"
    "gstreamer"
    "gst-libav"
    "gst-plugins-base"
    "gst-plugins-base-libs"
    "gst-plugins-good"
    "gst-plugins-bad"
)
makedepends=(
    "python2-distribute"
)
optdepends=(
    "python2-pygame: Starting sound support"
    "python2-raspberry-gpio: Raspberry Pi LED support"
    "python2-bbio: BeagleBone Black LED support"
)
provides=("dashcam")
conflicts=("dashcam")
source=("${url}/archive/${pkgver}.tar.gz")
sha256sums=("71ed97a1f872bd23046756600d39fa08498980e9835abbe3a549e6836aeba1d0")
backup=("etc/dashcam.conf")

build() {
  cd "${srcdir}/${pkgname}-${pkgver}"
  make
}

package() {
  cd "${srcdir}/${pkgname}-${pkgver}"
  make DESTDIR="${pkgdir}" install
}
