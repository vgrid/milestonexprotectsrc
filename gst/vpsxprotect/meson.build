# Define source code
gst_vpsxprotect_sources = [
  'GenericByteData.cpp',
  'gstvpsfromxprotectconverter.cpp',
  'gstvpsxprotect.cpp'
]

gst_vpsxprotect_headers = [
  'GenericByteData.h',
  'gstvpsfromxprotectconverter.h',
  'gstvpsxprotect.h'
]

# Build plugin library
gst_vpsxprotect_lib = library('gstvpsxprotect',
  gst_vpsxprotect_sources,
  c_args : gst_c_args,
  include_directories : configinc,
  install : true,
  install_dir : plugin_install_dir,
  dependencies : [gst_app_dep],
)

# Define the library as an internal dependency to the current build
vpsxprotect_dep = declare_dependency(link_with: gst_vpsxprotect_lib,
  dependencies : [glib_dep, gst_app_dep, gstbase_dep])