/**
  * SECTION:element-fromxprotectconverter
  *
  * The element fromxprotectconverter strips off the XProtect Generic Byte Data Header
  * from the video frames.
  *
  * <refsect2>
  * <title>Example launch line</title>
  * |[
  * gst-launch -v -m fakesrc ! fromxprotectconverter ! fakesink
  * ]|
  * </refsect2>
  */

#ifdef HAVE_CONFIG_H
#  include <config.h>
#endif

#include <inttypes.h>
#include <stdio.h>
#include <gst/gst.h>
#include "GenericByteData.h"
#include "gstvpsfromxprotectconverter.h"
#include "gstvpsxprotect.h"

  /* Filter signals and args */
enum
{
  /* FILL ME */
  LAST_SIGNAL
};

enum
{
  PROP_0,
};

/* the capabilities of the inputs and outputs.
 *
 * describe the real formats here.
 */
static GstStaticPadTemplate sink_template = GST_STATIC_PAD_TEMPLATE("sink",
  GST_PAD_SINK,
  GST_PAD_ALWAYS,
  GST_STATIC_CAPS("application/x-genericbytedata-octet-stream")
);

static GstStaticPadTemplate src_template =
    GST_STATIC_PAD_TEMPLATE ("src",
    GST_PAD_SRC,
    GST_PAD_SOMETIMES,
    GST_STATIC_CAPS ("video/x-h264; "
        "video/x-h265; "
        "image/jpeg;")
    );


#define gst_fromxprotectconverter_parent_class parent_class
G_DEFINE_TYPE(GstFromXprotectConverter, gst_fromxprotectconverter, GST_TYPE_BIN);

static gboolean gst_fromxprotectconverter_sink_event(GstPad * pad, GstObject * parent, GstEvent * event);
static GstFlowReturn gst_fromxprotectconverter_chain(GstPad * pad, GstObject * parent, GstBuffer * buf);

/* GObject vmethod implementations */

/* initialize the fromxprotectconverter's class */
static void
gst_fromxprotectconverter_class_init(GstFromXprotectConverterClass * klass)
{
  GST_DEBUG_CATEGORY_INIT(gst_xprotect_debug, "xprotect",
    0, "Template fromxprotectconverter");
  GstElementClass *gstelement_class;
  gstelement_class = (GstElementClass *)klass;

  gst_element_class_set_details_simple(gstelement_class,
    "fromxprotectconverter",
    "VPS/test",
    "Will remove a generic bytedata header from the frame.",
    "developer.milestonesys.com");

  gst_element_class_add_static_pad_template(gstelement_class,
    &sink_template);
  
  gst_element_class_add_static_pad_template(gstelement_class,
    &src_template);
}

/* initialize the new element
 * instantiate pads and add them to element
 * set pad calback functions
 * initialize instance structure
 */
static void gst_fromxprotectconverter_init(GstFromXprotectConverter * filter)
{
  if (filter == NULL)
  {
    GST_ERROR("Filter parameter was NULL.");
    return;
  }
  filter->srcpad_video = gst_pad_new_from_static_template(&src_template, "src");
  filter->sinkpad = gst_pad_new_from_static_template(&sink_template, "sink");
  gst_pad_set_event_function(filter->sinkpad,
    GST_DEBUG_FUNCPTR(gst_fromxprotectconverter_sink_event));
  gst_pad_set_chain_function(filter->sinkpad,
    GST_DEBUG_FUNCPTR(gst_fromxprotectconverter_chain));
  // GST_PAD_SET_PROXY_CAPS(filter->sinkpad);
  gst_pad_use_fixed_caps(filter->sinkpad);
  gst_element_add_pad(GST_ELEMENT(filter), filter->sinkpad);

  filter->firstrun = TRUE;
}

/* this function handles sink events */
static gboolean
gst_fromxprotectconverter_sink_event(GstPad * pad, GstObject * parent, GstEvent * event)
{
  GstFromXprotectConverter *filter;
  gboolean ret;

  filter = GST_FROMXPROTECTCONVERTER(parent);

  GST_LOG_OBJECT(filter, "Received %s event: %" GST_PTR_FORMAT,
    GST_EVENT_TYPE_NAME(event), event);

  switch (GST_EVENT_TYPE(event)) {
  case GST_EVENT_CAPS:
  {
    // GstCaps * caps;

    // gst_event_parse_caps(event, &caps);
    /* do something with the caps */

    /* and forward */
    // ret = gst_pad_event_default(pad, parent, event);
    gst_event_unref(event);
    ret = TRUE;
    break;
  }
  case GST_EVENT_RECONFIGURE:
  {
    gst_event_unref(event);
    ret = TRUE;
    break;
  }
  default:
    ret = gst_pad_event_default(pad, parent, event);
    break;
  }
  return ret;
}

/* chain function
 * this function does the actual processing
 */
static GstFlowReturn gst_fromxprotectconverter_chain(GstPad * pad, GstObject * parent, GstBuffer * buf)
{
  GstFromXprotectConverter *filter;
  GstCaps *caps = NULL;

  filter = GST_FROMXPROTECTCONVERTER(parent);

  GstMapInfo info;
  gst_buffer_map(buf, &info, GST_MAP_READ);

  VpsUtilities::GenericByteData * gbd = new VpsUtilities::GenericByteData((unsigned char*)info.data, (unsigned int) info.size, false, false);

  // TODO: Not sure how we should skip pushing a buffer?
  if (gbd->GetDataType() != VpsUtilities::DataType::VIDEO) {
    gst_buffer_unmap(buf, &info);
    gst_buffer_unref(buf);
    delete gbd;
    return GST_FLOW_OK;
  }

  if (filter->firstrun) {
    GstSegment segment;

    switch(gbd->GetCodec()) {
      case VpsUtilities::Codec::H264:
        caps = gst_caps_new_empty_simple ("video/x-h264");
        break;
      case VpsUtilities::Codec::H265:
        caps = gst_caps_new_empty_simple ("video/x-h265");
        break;
      case VpsUtilities::Codec::JPEG:
        caps = gst_caps_new_empty_simple ("image/jpeg");
        break;
      default:
        gst_buffer_unmap(buf, &info);
        gst_buffer_unref(buf);
        delete gbd;
        return GST_FLOW_NOT_SUPPORTED;
    }

    gst_pad_use_fixed_caps (filter->srcpad_video);
    gst_pad_set_active (filter->srcpad_video, TRUE);

    // Send events to tell the rest of the pipeline we're configured and ready to go
    GstEvent *stream_start = gst_event_new_stream_start ("src");
    gst_event_set_group_id(stream_start, gst_util_group_id_next ());
    gst_pad_push_event (filter->srcpad_video, stream_start);

    gst_pad_set_caps(filter->srcpad_video, caps);

    gst_segment_init (&segment, GST_FORMAT_BYTES);
    gst_pad_push_event (filter->srcpad_video, gst_event_new_segment (&segment));

    gst_element_add_pad(GST_ELEMENT(filter), filter->srcpad_video);

    filter->firstrun = FALSE;

    GST_DEBUG_OBJECT (filter, "emitting no more pads");
    gst_element_no_more_pads (GST_ELEMENT (filter));

    if (caps)
      gst_caps_unref (caps);
  }

  GstBuffer * outputBuffer = gst_buffer_new();
  GstMemory * mem = gst_allocator_alloc(NULL, gbd->GetBodyLength(), NULL);
  gst_buffer_append_memory(outputBuffer, mem);
  GstMapInfo info2;
  gst_buffer_map(outputBuffer, &info2, GST_MAP_WRITE);

  GST_TRACE_OBJECT(gst_xprotect_debug, "FROM seq no: %u\n", gbd->GetSequenceNumber());
  GST_TRACE_OBJECT(gst_xprotect_debug, "FROM Sync ts no: %" PRIu64 "\n", gbd->GetSyncTimeStamp());
  GST_TRACE_OBJECT(gst_xprotect_debug, "FROM ts no: %" PRIu64 "\n", gbd->GetTimeStamp());

  GST_BUFFER_DTS(outputBuffer) = GST_BUFFER_DTS(buf);
  GST_BUFFER_PTS(outputBuffer) = GST_BUFFER_PTS(buf);
  GST_BUFFER_OFFSET(outputBuffer) = GST_BUFFER_OFFSET(buf);

  // Theoretically, we can just modify the buffer in-place
  // TODO: Look into this
  memcpy(info2.data, gbd->GetBody(), gbd->GetBodyLength());

  delete gbd;

  gst_buffer_unmap(outputBuffer, &info2);

  gst_buffer_unmap(buf, &info);
  gst_buffer_unref(buf);
  
  return gst_pad_push(filter->srcpad_video, outputBuffer);
}
