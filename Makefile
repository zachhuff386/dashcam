CC = gcc
CFLAGS = -O3 `pkg-config --cflags --libs gstreamer-1.0`
RM = rm -f
RMR = rm -f -r
MKDIR = mkdir -p
TOUCH = touch
PYTHON = python2 setup.py

OBJS = \
	obj/dashcam-stream.o

HEADERS = \
	src/dashcam-stream.h

ifneq ($(DESTDIR),)
    PYTHON_ROOT = --root=$(DESTDIR)
endif

all: build/dashcam-stream

build/dashcam-stream: src/dashcam-stream.c src/dashcam-stream.h
	$(MKDIR) build
	$(CC) $(CFLAGS) -o $@ $^
	$(PYTHON) build

install: all
	$(PYTHON) install $(PYTHON_ROOT) --prefix=/usr
	$(TOUCH) $(DESTDIR)/etc/dashcam.confc
	$(MKDIR) $(DESTDIR)/var/log
	$(TOUCH) $(DESTDIR)/var/log/dashcam.log

uninstall:
	$(RM) $(DESTDIR)/etc/dashcam.conf
	$(RM) $(DESTDIR)/etc/dashcam.confc
	$(RM) $(DESTDIR)/etc/systemd/system/dashcamd.service
	$(RM) $(DESTDIR)/usr/bin/dashcam
	$(RM) $(DESTDIR)/usr/bin/dashcam-stream
	$(RMR) $(DESTDIR)/usr/share/dashcam
	$(RMR) $(DESTDIR)/usr/lib/python2.7/site-packages/dashcam
	$(RM) $(DESTDIR)/usr/lib/python2.7/site-packages/dashcam-*-py2.7.egg-info
	$(RM) $(DESTDIR)/var/log/dashcam.log

clean:
	$(RMR) build
