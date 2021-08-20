# milestonexprotectsrc
gstreamer element to pull genericbytedata from Milestone XProtect. Requires the `gst-python` bindings be installed correctly. This also includes the `fromxprotectconverter` element to convert the GenericByteData into a pad with either h264, h265 or jpeg on the caps


## Installation Instructions

Clone the repository to desired location:

`git clone https://github.com/vgrid/milestonexprotectsrc`

Run (with `build-essential`, `libglib2.0-dev`, `liborc-0.4-dev`) make

`make && make install`

By default, this will install the elements into `/usr/lib/gstreamer-1.0`. Python modules rely on this to work, so you'll need to:

`export GST_PLUGIN_PATH=$GST_PLUGIN_PATH:/usr/lib/gstreamer-1.0`

## Usage

Example launch line:

`gst-launch-1.0 milestonexprotectsrc user-domain=DOMAIN user-id=user user-pw=password camera-id=173cb77c-4883-4519-ae94-48a8e574afe9 ! fromxprotectconverter ! fakesink`