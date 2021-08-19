# milestonexprotectsrc
gstreamer element to pull genericbytedata from Milestone XProtect. Requires the `gst-python` bindings be installed correctly. As this outputs the GenericByteData interface, you'll need another filter to transform this into the relevant data (and caps)


## Installation Instructions

Clone the repository to desired location:

`git clone https://github.com/vgrid/milestonexprotectsrc /usr/src/milestonexprotectsrc`

Install the required python modules:

`pip3 install -r requirements.txt`

Set the gstreamer environment variable to look at that path for the plugin (note that the python bindings *expect* there to be a python folder underneath, so don't include that in the path):

`export GST_PLUGIN_PATH=$GST_PLUGIN_PATH:/usr/src/milestonexprotect`

## Usage

Example launch line:

`gst-launch-1.0 milestonexprotectsrc user-domain=DOMAIN user-id=user user-pw=password camera-id=173cb77c-4883-4519-ae94-48a8e574afe9 ! fakesink`