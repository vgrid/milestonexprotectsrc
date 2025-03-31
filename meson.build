project('milestonexprotectsrc', 'cpp',
  version : '1.0.0',
  meson_version : '>= 0.51'
)

gst_milestonexprotect_version = meson.project_version()
version_arr = gst_milestonexprotect_version.split('.')
gst_milestonexprotect_version_major = version_arr[0].to_int()
gst_milestonexprotect_version_minor = version_arr[1].to_int()
gst_milestonexprotect_version_micro = version_arr[2].to_int()
if version_arr.length() == 4
  gst_milestonexprotect_version_nano = version_arr[3].to_int()
else
  gst_milestonexprotect_version_nano = 0
endif
gst_milestonexprotect_version_is_dev = gst_milestonexprotect_version_minor % 2 == 1 and gst_milestonexprotect_version_micro < 90

# Find external dependencies
gst_req = '>=1.16.0'
gst_app_dep = dependency('gstreamer-app-1.0', version : gst_req)
gst_dep = dependency('gstreamer-1.0', version : gst_req,
  fallback : ['gstreamer', 'gst_dep'])
gstbase_dep = dependency('gstreamer-base-1.0', version : gst_req,
  fallback : ['gstreamer', 'gst_base_dep'])
glib_dep = dependency('glib-2.0')

# Define compiler args and include directories
gst_c_args = ['-DHAVE_CONFIG_H']
configinc = include_directories('.')

# Define gstreamer API version
apiversion = '1.0'

# Define installation directories
prefix = get_option('prefix')
plugin_install_dir = join_paths(prefix, get_option('libdir'), 'gstreamer-1.0')

# Get an object returns describing a compiler
cc = meson.get_compiler('cpp')

# Verify if the warning flags are available in the compiler
# If the flags is availale for the compiler it wiil be used in all compiler
# invocations with the exception of compile tests.
supported_warning_flags = cc.get_supported_arguments(
  '-Wmissing-declarations',
  '-Wmissing-prototypes',
  '-Wredundant-decls',
  '-Wundef',
  '-Wwrite-strings',
  '-Wformat',
  '-Wformat-nonliteral',
  '-Wformat-security',
  '-Wold-style-definition',
  '-Winit-self',
  '-Wmissing-include-dirs',
  '-Waddress',
  '-Waggregate-return',
  '-Wno-multichar',
  '-Wdeclaration-after-statement',
  '-Wvla',
  '-Wpointer-arith',
)

add_project_arguments([supported_warning_flags], language: 'cpp')

# Create an empty configuration object to set config.h information
cdata = configuration_data()

pkg_url='://www.github.com/vgrid/milestonexprotectsrc'
# Set config.h information
cdata.set_quoted('GST_API_VERSION', apiversion)
cdata.set_quoted('LOCALEDIR', join_paths(prefix, get_option('localedir')))
cdata.set_quoted('LIBDIR', join_paths(prefix, get_option('libdir')))
cdata.set_quoted('GST_API_VERSION', '1.0')
cdata.set_quoted('GST_LICENSE', 'LGPL')
cdata.set_quoted('PACKAGE', 'gst-milestonexprotect')
cdata.set_quoted('PACKAGE_NAME', 'GstXProtect')
cdata.set_quoted('PACKAGE_STRING', 'GstXProtect @0@'.format(gst_milestonexprotect_version))
cdata.set_quoted('PACKAGE_TARNAME', 'gst-milestonexprotect')
cdata.set_quoted('PACKAGE_BUGREPORT', pkg_url)
cdata.set_quoted('PACKAGE_URL', pkg_url)
cdata.set_quoted('PACKAGE_VERSION', gst_milestonexprotect_version)
cdata.set_quoted('PLUGINDIR', plugin_install_dir)
cdata.set_quoted('VERSION', gst_milestonexprotect_version)

if gst_milestonexprotect_version_nano > 0
    # Have GST_ERROR message printed when running from git
    cdata.set('GST_LEVEL_DEFAULT', 'GST_LEVEL_ERROR')
else
    cdata.set('GST_LEVEL_DEFAULT', 'GST_LEVEL_NONE')
endif

# GStreamer package name and origin url
gst_package_name = get_option('package-name')
if gst_package_name == ''
  if gst_milestonexprotect_version_nano == 0
    gst_package_name = 'GstXProtect'
  elif gst_milestonexprotect_version_nano == 1
    gst_package_name = 'GstXProtect'
  else
    gst_package_name = 'GstXProtect'
  endif
endif
cdata.set_quoted('GST_PACKAGE_NAME', gst_package_name)
cdata.set_quoted('GST_PACKAGE_ORIGIN', get_option('package-origin'))

# These are only needed/used by the ABI tests
host_defines = [
  [ 'x86', 'HAVE_CPU_I386' ],
  [ 'x86_64', 'HAVE_CPU_X86_64' ],
  [ 'arm', 'HAVE_CPU_ARM' ],
  [ 'aarch64', 'HAVE_CPU_AARCH64' ],
  [ 'mips', 'HAVE_CPU_MIPS' ],
  [ 'powerpc', 'HAVE_CPU_PPC' ],
  [ 'powerpc64', 'HAVE_CPU_PPC64' ],
  [ 'alpha', 'HAVE_CPU_ALPHA' ],
  [ 'sparc', 'HAVE_CPU_SPARC' ],
  [ 'ia64', 'HAVE_CPU_IA64' ],
  [ 'hppa', 'HAVE_CPU_HPPA' ],
  [ 'm68k', 'HAVE_CPU_M68K' ],
  [ 's390', 'HAVE_CPU_S390' ],
]
foreach h : host_defines
  if h.get(0) == host_machine.cpu()
    cdata.set(h.get(1), 1)
  else
    cdata.set(h.get(1), false)
  endif
endforeach

cdata.set_quoted('HOST_CPU', host_machine.cpu())

# Verify if the specified header exists
check_headers = [
  'cstdint',
  'string.h',
  'inttypes.h',
  'stdio.h'
]

foreach h : check_headers
  if cc.has_header(h)
    define = 'HAVE_' + h.underscorify().to_upper()
    cdata.set(define, 1)
  endif
endforeach

# Enter to each subdirectory and execute the meson.build
subdir('gst')

# Meson will generate a header file all the entries in the configuration data object
configure_file(output : 'config.h', configuration : cdata)