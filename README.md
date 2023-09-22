# milestonexprotectsrc
gstreamer element to pull genericbytedata from Milestone XProtect. Requires the `gst-python` bindings be installed correctly. This also includes the `fromxprotectconverter` element to convert the GenericByteData into a pad with either h264, h265 or jpeg on the caps


## Installation Instructions

Clone the repository to desired location, making sure that you have GStreamer, GStreamer Python Bindings, Python3 and meson/ninja installed (these will all be checked and fail if not):

```
git clone https://github.com/vgrid/milestonexprotectsrc

meson builddir
meson compile -C builddir
meson install -C builddir
```


## Usage

Example launch line:

`gst-launch-1.0 milestonexprotectsrc management-server=10.1.1.1 user-domain=DOMAIN user-id=user user-pw=password camera-id=173cb77c-4883-4519-ae94-48a8e574afe9 ! fromxprotectconverter ! fakesink`

## Options

* `management-server`: IP or DNS Name of Management Server
* `user-domain`: Domain name to log in with, or **BASIC** to make it use basic auth
* `user-id`: Username for Windows/Milestone user
* `user-pw`: Password for Windows/Milestone user
* `camera-id`: GUID of the camera to stream
* `force-management-address`: Ensures that the management server you supplied in `management-server` is used for SOAP requests. Sometimes required if DNS doesn't resolve

## Misc Info

`fromxprotectconverter` automatically detects the incoming video payload, and provides `SOMETIMES` caps to GStreamer. If you're using this programmatically, you'll have to listen to the `pad-added` event to get the pad that provides either `video/x-h264`, `video/x-h265` or `image/jpeg`

## Action Signals

### ptz
If you emit a `ptz` signal to the element, with a `Gst.Structure` named `PTZCommand`, with values `x`, `y` and `z`, then the element will connect to the `RecorderCommandService` (SOAP) and send the PTZ command. These values should be -1 to 1.

Send `x`, `y` and `z` set to 0 to stop the PTZ from moving