from datetime import datetime, timedelta
import gi
from pytz import UTC
from requests import auth, Session
from requests_ntlm import HttpNtlmAuth
from socket import *
from urllib.parse import urlparse
import uuid
import urllib3
import xml.etree.ElementTree as ET
from zeep import Client
from zeep.cache import SqliteCache
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
    try:
      buf = self.get_buffer()
    except:
     raise
    if buf is None:
      return buf

    # If we can't decode, just try again
    try:
      decode = buf.decode().strip()
      return decode
    except:
      return self.get_line()

  def get_buffer(self):
    while b'\r\n\r\n' not in self.buffer:
      try:
        data = self.sock.recv(1024)
      except:
        raise
      if not data: # socket closed
        return None
      self.buffer += data
    buf,sep,self.buffer = self.buffer.partition(b'\r\n\r\n')
    return buf

  def get_buffer_size(self, size: int):
    while len(self.buffer) < size:
      try:
        data = self.sock.recv(4096)
      except:
        raise
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
                 """Milestone GUID of the Camera object to stream.
                 If this is supplied but the hardware-id isn't, this trawls through the whole Milestone configuration to find the hardware and associated recorder, 
                 which could be slower on larger sites""",
                 "",
                 GObject.ParamFlags.READWRITE
                ),
        "hardware-id": (str,
                 "Hardware ID",
                 "Milestone GUID of the Hardware object to stream. If this is supplied then the cameraId must be supplied too",
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
        "timeout": (float,
                 "timeout",
                 "Timeout in seconds to wait to connect or receive packets (0 disables timeout)",
                 0.0,
                 3.0,
                 2.0,
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
        self.hardware_id: str = ""
        self.camera_id: str = ""
        self.force_management_address: bool = False
        self.timeout: float = 2.0

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
        elif prop.name == 'hardware-id':
            return self.hardware_id
        elif prop.name == 'camera-id':
            return self.camera_id
        elif prop.name == 'force-management-address':
            return self.force_management_address
        elif prop.name == 'timeout':
            return self.timeout
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
        elif prop.name == 'hardware-id':
            self.hardware_id = value
        elif prop.name == 'camera-id':
            self.camera_id = value
        elif prop.name == 'force-management-address':
            self.force_management_address = value
        elif prop.name == 'timeout':
            self.timeout = value
        else:
            raise AttributeError('unknown property %s' % prop.name)

    def do_start (self):
      if self.camera_id == "" and self.hardware_id != "":
        return False

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

      try:
        Gst.info("Instantiating SOAP Client")
        self.client = Client(url + "?wsdl", transport=Transport(cache=SqliteCache(), session=session))
      except:
        Gst.error("Error getting WSDL - check authentication?")
        return False
      self.instance_id = str(uuid.uuid4())

      if self.force_management_address:
        self.service = self.client.create_service(binding_override_namespace, url)
      else:
        self.service = self.client.service

      Gst.info("Performing login")
      login = self.service.Login(instanceId=self.instance_id)
      self.login_token: str = login.Token
      self.renew_time: datetime = login.RegistrationTime + timedelta(microseconds=login.TimeToLive.MicroSeconds) - timedelta(seconds=60)

      # Work out which way we should obtain the recorder configuration
      # If we have the hardware ID, get it directly (and then set the camera-id if it was blank)
      if self.hardware_id != "":
        Gst.info("Have a hardware ID, so getting harware config directly")
        # array_of_guid = self.client.get_type('ns0:ArrayOfGuid')
        hardware_ids = {"guid": [self.hardware_id]}
        hardware_info = self.service.GetConfigurationHardware(login.Token, hardware_ids)
        if len(hardware_info) < 1:
          Gst.error("Hardware ID not found")
          return False

        # Check the cameraId is mapped to the hardwareId
        if self.camera_id != "":
          if self.camera_id.lower() not in hardware_info[0].DeviceIds.guid:
            Gst.error("Camera ID supplied not found for that Hardware ID")
            return False

        Gst.info("Getting recording server information")
        recorder_info = self.service.QueryRecorderInfo(login.Token, hardware_info[0].RecorderId)

        recorder_url = recorder_info.WebServerUri

      # Fallback to trawling through the whole configuration
      else:
        Gst.info("No Hardware ID supplied, getting whole site configuration")
        config = self.service.GetConfiguration(token=login.Token)
        Gst.info("Got site config")
        recorder_url = None
        for recorder in config.Recorders.RecorderInfo:
          for camera in recorder.Cameras.CameraInfo:
            if camera.DeviceId.lower() == self.camera_id.lower():
              recorder_url = recorder.WebServerUri
              break

        if recorder_url is None:
          Gst.error("Recorder for camera not found")
          return False

      recorder_result = urlparse(recorder_url)

      self.recorder_host = recorder_result.hostname
      self.recorder_port = recorder_result.port

      self.socket = socket()
      if self.timeout != 0.0:
        self.socket.settimeout(self.timeout)
      try:
        Gst.info("Connecting to recording server %s:%d" % (self.recorder_host, self.recorder_port))
        self.socket.connect((self.recorder_host, self.recorder_port))
      except:
        return False

      self.buffer = Buffer(self.socket)
      self.xmlGenerator = XmlGenerator(self.login_token, self.camera_id)

      # Send the initial connect to make sure we're good to go
      self.socket.sendall(bytes(self.xmlGenerator.connect(), 'UTF-8'))
      self.socket.sendall(b'\r\n\r\n')

      response = self.buffer.get_line()
      root = ET.fromstring(response)
      elem = root.find('connected')
      if elem is None or elem.text != 'yes':
        Gst.error("Unable to connect to recording server")
        return False

      Gst.info("Recording server connected")
      return True

    def renew_token(self):
      Gst.info("Renewing token")
      login = self.service.Login(instanceId=self.instance_id, currentToken=self.login_token)
      self.login_token = login.Token
      self.renew_time: datetime = login.RegistrationTime + timedelta(microseconds=login.TimeToLive.MicroSeconds) - timedelta(seconds=60)
      self.socket.sendall(bytes(self.xmlGenerator.connect_update(), 'UTF-8'))
      self.socket.sendall(b'\r\n\r\n')

    # This method is called by gstreamer to create a buffer
    def do_create(self, o, s):
      if self.started == False:
        Gst.info("Sending start live command")
        self.socket.sendall(bytes(self.xmlGenerator.live(), 'UTF-8'))
        self.socket.sendall(b'\r\n\r\n')
        self.started = True

      while True:
        if self.renew_time < datetime.now(UTC):
          Gst.info("Renewing token with management server")
          self.renew_token()

        try:
          response = self.buffer.get_line()
        except Exception as inst:
          Gst.error("Error getting data from recording server - %s" % type(inst).__name__)
          return (Gst.FlowReturn.EOS, None)
        # Socket closed, return with an EOS
        if response is None:
          Gst.error("Socket with recording server closed")
          return (Gst.FlowReturn.EOS, None)
        try:
          if response.startswith("ImageResponse"):
            lines = response.splitlines()
            headers = {}
            for i in range(1, len(lines)):
              key, val = lines[i].split(": ")
              headers[key.lower()] = val

            size = int(headers["content-length"])

            Gst.trace("ImageResponse received\n%s" % response)

            mbytes = self.buffer.get_buffer_size(size)
            buf = Gst.Buffer.new_wrapped(mbytes)
            return (Gst.FlowReturn.OK, buf)

          elif response.startswith("<?xml"):
            try:
              root = ET.fromstring(response)
              if root.tag == 'livepackage':
                Gst.debug("livepackage received\n%s" % response)
                continue

              # this is a response to a connectupdate
              if root.tag == 'methodresponse':
                elem = root.find('methodname')
                if elem is not None and elem.text == "connectupdate":
                  elem = root.find("connected")
                  if elem is not None and elem.text == 'yes':
                    # Success on the connectupdate - just ignore
                    continue
                  else:
                    # Error doing a connectupdate
                    Gst.error("connectupdate failed %s" % response)
                    break

                Gst.warning("Unknown methodresponse - %s" % response)
                continue

            except:
              Gst.error("Unknown methodresponse - %s" % response)
              break

          else:
            if response == "":
              continue

            Gst.warning("Unknown response %s" % str(response))
            continue

        except Exception as inst:
          Gst.error("Unknown exception encountered - %s" % type(inst).__name__)
          break

      return (Gst.FlowReturn.ERROR, None)

__gstelementfactory__ = ("milestonexprotectsrc", Gst.Rank.NONE, MilestoneXprotectSrc)