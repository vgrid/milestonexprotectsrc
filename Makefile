CC = g++
GSTREAMER = `pkg-config --cflags --libs gstreamer-1.0 gstreamer-video-1.0`
FLAGS = -fPIC

.DEFAULT_GOAL := all

ifeq ($(OUTDIR),)
	OUTDIR=./bin
endif

setup-outdir:
	@mkdir -p $(OUTDIR)

OUTFILE = $(OUTDIR)/libgstvpsxprotect.so
INPUT = GenericByteData.h GenericByteData.cpp gstvpsfromxprotectconverter.h gstvpsfromxprotectconverter.cpp gstvpsxprotect.cpp gstvpsxprotect.h
OUTPUT = -shared -o  $(OUTFILE)

all: setup-outdir
	$(CC) $(OUTPUT) $(FLAGS) $(INPUT) $(INCLUDE) $(GSTREAMER)

install:
	cp $(OUTFILE) /usr/lib/gstreamer-1.0/
	mkdir -p /usr/lib/gstreamer-1.0/python
	cp python/milestonexprotect.py /usr/lib/gstreamer-1.0/python/
	pip3 install -r requirements.txt

clean:
	@rm -f $(OUTFILE)
