python = import('python') # Meson new Python module https://mesonbuild.com/Python-module.html

# Python 3 required modules
python3_required_modules = ['gi']
python3 = python.find_installation('python3', modules: python3_required_modules)

# Check we have the required gstreamer python bindings
script = 'import gi; gi.require_version(\'Gst\', \'1.0\'); gi.require_version(\'GstBase\', \'1.0\'); from gi.repository import Gst, GObject, GstBase'
if run_command(python3, '-c', script, check: false).returncode() != 0
  error('Required GStreamer Python bindings not found')
endif

# Install the required dependencies
if get_option('install-python-requirements')
  meson.add_install_script('install_requirements.sh')
endif

install_files = ['milestonexprotect.py', 'milestonexprotect_requirements.txt']

install_data(
    install_files,
    install_dir: join_paths(plugin_install_dir, 'python')
)

# Define the library as an internal dependency to the current build
vpsxprotect_dep = declare_dependency(dependencies : [gst_app_dep, gstbase_dep])