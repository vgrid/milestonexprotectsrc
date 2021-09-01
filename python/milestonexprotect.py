from datetime import timedelta
import gi
from requests import auth, Session
from requests_ntlm import HttpNtlmAuth
from socket import *
from urllib.parse import urlparse
import uuid
import urllib3
import xml.etree.ElementTree as ET
from zeep import Client
from zeep.transports import Transport

gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
gi.require_version('GstAudio', '1.0')

from gi.repository import Gst, GLib, GObject, GstBase, GstAudio

OCAPS = Gst.Caps.from_string (
        'application/x-genericbytedata-octet-stream')

class Buffer:
  def __init__(self,sock):
    self.sock = sock
    self.buffer = b''

  def get_line(self):
    buf = self.get_buffer()
    return buf.decode().strip()

  def get_buffer(self):
    while b'\r\n\r\n' not in self.buffer:
      data = self.sock.recv(1024)
      if not data: # socket closed
        return None
      self.buffer += data
    buf,sep,self.buffer = self.buffer.partition(b'\r\n\r\n')
    return buf 

  def get_buffer_size(self, size: int):    
    while len(self.buffer) < size:
      data = self.sock.recv(4096)
      if not data: # socket closed
        return None
      self.buffer += data
    buf,sep,self.buffer = self.buffer.partition(b'\r\n\r\n')
    return buf

class XmlGenerator:
  def __init__(self, token, camera_id):
    self._request_id = 1

    self._camera_id = camera_id
    self._token = token

  def connect(self):
    self._request_id += 1
    return """<?xml version="1.0" encoding="UTF-8"?>
<methodcall>
<requestid>{request_id}</requestid>
<methodname>connect</methodname>
<username>a</username>
<password>a</password>
<cameraid>a</cameraid>
<alwaysstdjpeg>no</alwaysstdjpeg>
<connectparam>id={camera_id}&amp;connectiontoken={token}</connectparam>
</methodcall>""".format(request_id=str(self._request_id), camera_id=self._camera_id, token=self._token).replace("\n", "")

  def connect_update(self):
    self._request_id += 1
    return """<?xml version="1.0" encoding="UTF-8"?>
<methodcall>
<requestid>{request_id}</requestid>
<methodname>connectupdate</methodname>
<connectparam>id={camera_id}&amp;connectiontoken={token}</connectparam>
</methodcall>""".format(request_id=str(self._request_id), camera_id=self._camera_id, token=self._token).replace("\n", "")

  def live(self):
    self._request_id += 1
    return """<?xml version="1.0" encoding="UTF-8"?>
<methodcall>
<requestid>{request_id}</requestid>
<methodname>live</methodname>
</methodcall>""".format(request_id=str(self._request_id)).replace("\n", "")


class MilestoneXprotectSrc(GstBase.BaseSrc):
    __gstmetadata__ = ('MilestoneXprotectSrc','Src', \
                      'Milestone XProtect Source Element', 'Chris Wiggins')

    __gproperties__ = {
        "management-server": (str,
                 "Management Server",
                 "Address of the Milestone XProtect Managment Server",
                 "",
                 GObject.ParamFlags.READWRITE
                ),
        "user-domain": (str,
                 "Domain",
                 "Domain to use to log in - if domain is set to BASIC, basic authentication against Milestone will be used",
                 "",
                 GObject.ParamFlags.READWRITE
                ),
        "user-id": (str,
                 "Username",
                 "Username to use to log in",
                 "",
                 GObject.ParamFlags.READWRITE
                ),
        "user-pw": (str,
                 "Password",
                 "Password to use to log in",
                 "",
                 GObject.ParamFlags.READWRITE
                ),
        "camera-id": (str,
                 "Camera ID",
                 "Milestone GUID of the Camera object to stream",
                 "",
                 GObject.ParamFlags.READWRITE
                ),
        "force-management-address": (bool,
                 "Force Management Address",
                 """Forces the SOAP login process to use the managment server supplied in the management-server property, rather than the one returned in the WSDL.
This can help when servers return a different hostname (i.e DNS instead of an IP) in the response, rather than the value you supply""",
                 False,
                 GObject.ParamFlags.READWRITE
                ),
    }

    __gsttemplates__ = Gst.PadTemplate.new("src",
                                           Gst.PadDirection.SRC,
                                           Gst.PadPresence.ALWAYS,
                                           OCAPS)

    def __init__(self):
        GstBase.BaseSrc.__init__(self)

        self.management_server: str = ""
        self.user_domain: str = ""
        self.user_id: str = ""
        self.user_pw: str = ""
        self.camera_id: str = ""
        self.force_management_address: bool = False

        self.set_live(True)
        self.set_do_timestamp(True)
        self.started = False

    def do_get_property(self, prop):
        if prop.name == 'management-server':
            return self.management_server
        elif prop.name == 'user-domain':
            return self.user_domain
        elif prop.name == 'user-id':
            return self.user_id
        elif prop.name == 'user-pw':
            return self.user_pw
        elif prop.name == 'camera-id':
            return self.camera_id
        elif prop.name == 'force-management-address':
            return self.force_management_address
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def do_set_property(self, prop, value):
        if prop.name == 'management-server':
            self.management_server = value
        elif prop.name == 'user-domain':
            self.user_domain = value
        elif prop.name == 'user-id':
            self.user_id = value
        elif prop.name == 'user-pw':
            self.user_pw = value
        elif prop.name == 'camera-id':
            self.camera_id = value
        elif prop.name == 'force-management-address':
            self.force_management_address = value
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def do_start (self):
      session = Session()
      if self.user_domain == "BASIC":
        url = "https://" + self.management_server + "/ManagementServer/ServerCommandService.svc"
        session.auth = auth.HTTPBasicAuth(username=self.user_id, password=self.user_pw)
        session.verify = False # Highly unlikely we'll trust the Milestone cert, so just ignore errors
        urllib3.disable_warnings()
        binding_override_namespace = "{http://tempuri.org/}BasicHttpBinding_IServerCommandService"
      else:
        # TODO: This endpoint is marked as deprecated, but testing against a 2020R3 release doesn't work with the new endpoint?
        url = "http://" + self.management_server + "/ServerAPI/ServerCommandService.asmx"
        session.auth = HttpNtlmAuth(self.user_domain + "\\" + self.user_id, self.user_pw)
        binding_override_namespace = "{http://videoos.net/2/XProtectCSServerCommand}ServerCommandServiceSoap"

      self.client = Client(url + "?wsdl", transport=Transport(session=session))
      self.instance_id = str(uuid.uuid4())

      if self.force_management_address:
        self.service = self.client.create_service(binding_override_namespace, url)
      else:
        self.service = self.client.service
      
      login = self.service.Login(instanceId=self.instance_id)
      self.login_token = login.Token
      self.renew_time = login.RegistrationTime + timedelta(microseconds=login.TimeToLive.MicroSeconds) - timedelta(seconds=60)

      config = self.service.GetConfiguration(token=login.Token)
      recorder_url = None
      for recorder in config.Recorders.RecorderInfo:
        for camera in recorder.Cameras.CameraInfo:
          if camera.DeviceId.lower() == self.camera_id.lower():
            recorder_url = recorder.WebServerUri
            break

      if recorder_url is None:
        return False

      recorder_result = urlparse(recorder_url)

      self.recorder_host = recorder_result.hostname
      self.recorder_port = recorder_result.port

      self.socket = socket()
      self.socket.connect((self.recorder_host, self.recorder_port))

      self.buffer = Buffer(self.socket)
      self.xmlGenerator = XmlGenerator(self.login_token, self.camera_id)
      
      # Send the initial connect to make sure we're good to go
      self.socket.sendall(bytes(self.xmlGenerator.connect(), 'UTF-8'))
      self.socket.sendall(b'\r\n\r\n')

      response = self.buffer.get_line()
      root = ET.fromstring(response)
      elem = root.find('connected')
      if elem is None or elem.text != 'yes':
        return False

      return True

    # TODO: Do renewal logic
    def renew_token(self):
      login = self.service.Login(instanceId=self.instance_id, currentToken=self.login_token)
      self.login_token = login.Token
      self.renew_time = login.RegistrationTime + timedelta(microseconds=login.TimeToLive.MicroSeconds) - timedelta(seconds=60)
      self.socket.sendall(bytes(self.xmlGenerator.connect_update(), 'UTF-8'))
      self.socket.sendall(b'\r\n\r\n')

    # This method is called by gstreamer to create a buffer
    def do_create(self, o, s):
      if self.started == False:
        self.socket.sendall(bytes(self.xmlGenerator.live(), 'UTF-8'))
        self.socket.sendall(b'\r\n\r\n')
        self.started = True

      while True:
        response = self.buffer.get_line()
        try:
          if response.startswith("ImageResponse"):
            lines = response.splitlines()
            headers = {}
            for i in range(1, len(lines)):
              key, val = lines[i].split(": ")
              headers[key.lower()] = val

            size = int(headers["content-length"])

            mbytes = self.buffer.get_buffer_size(size)
            buf = Gst.Buffer.new_wrapped(mbytes)
            return (Gst.FlowReturn.OK, buf)

          elif response.startswith("<?xml"):
            continue

          else:
            if response == "":
              continue

            print("Unknown data")
            print (response)
            continue

        except Exception as inst:
          print("Hit an error")
          print(response)
          print (type(inst))
          break

      print ("returning")
      return Gst.FlowReturn.ERROR

__gstelementfactory__ = ("milestonexprotectsrc", Gst.Rank.NONE, MilestoneXprotectSrc)