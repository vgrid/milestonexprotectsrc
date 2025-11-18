#ifndef __GST_FROMXPROTECTCONVERTER_H__
#define __GST_FROMXPROTECTCONVERTER_H__

#include <gst/gst.h>

G_BEGIN_DECLS

/* #defines don't like whitespacey bits */
#define GST_TYPE_FROMXPROTECTCONVERTER \
  (gst_fromxprotectconverter_get_type())

#define GST_FROMXPROTECTCONVERTER(obj) \
  (G_TYPE_CHECK_INSTANCE_CAST((obj),GST_TYPE_FROMXPROTECTCONVERTER,GstFromXprotectConverter))

#define GST_FROMXPROTECTCONVERTER_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_CAST((klass),GST_TYPE_FROMXPROTECTCONVERTER,GstFromXprotectConverterClass))

#define GST_IS_FROMXPROTECTCONVERTER(obj) \
  (G_TYPE_CHECK_INSTANCE_TYPE((obj),GST_TYPE_FROMXPROTECTCONVERTER))

#define GST_IS_FROMXPROTECTCONVERTER_CLASS(klass) \
  (G_TYPE_CHECK_CLASS_TYPE((klass),GST_TYPE_FROMXPROTECTCONVERTER))

typedef struct _GstFromXprotectConverter      GstFromXprotectConverter;
typedef struct _GstFromXprotectConverterClass GstFromXprotectConverterClass;

struct _GstFromXprotectConverter
{
  GstBin bin;
  gboolean firstrun;
  GstPad *sinkpad, *srcpad_video, *srcpad_metadata;
};

struct _GstFromXprotectConverterClass
{
  GstBinClass parent_class;
};

GType gst_fromxprotectconverter_get_type(void);

G_END_DECLS

#endif /* __GST_XPROTECT_H__ */

