from datetime import datetime, timedelta
import gi
import re
from inspect import currentframe
from pytz import UTC
from requests import auth, Session
from requests.adapters import HTTPAdapter
from requests_ntlm import HttpNtlmAuth
from socket import *
import ssl
from urllib.parse import urlparse
import uuid
import urllib3
import xml.etree.ElementTree as ET
from zeep import Client
from zeep.cache import SqliteCache
from zeep.transports import Transport

gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')

from gi.repository import Gst, GObject, GstBase

OCAPS = Gst.Caps.from_string (
        'application/x-genericbytedata-octet-stream')


# Global SSL context to use for requests library, and our own socket
ssl_context = ssl._create_unverified_context()
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_1
ssl_context.set_ciphers("DEFAULT:@SECLEVEL=0") # OpenSSL 3.0.1 moved TLS1.1 to SEC level 0

# Class to take the SSL context and apply it for requests library
class SSLAdapter(HTTPAdapter):
  def init_poolmanager(self, *args, **kwargs):
    kwargs["ssl_context"] = ssl_context
    return super().init_poolmanager(*args, **kwargs)

# Function to add a message to the element
def element_message(element, domain, code, message, debug=None, message_type="error"):
  cf = currentframe()
  if cf and cf.f_back:
    filename = cf.f_back.f_code.co_filename
    function = cf.f_back.f_code.co_name
    line = cf.f_back.f_lineno

    if message_type == "error":
      element.message_full(Gst.MessageType.ERROR, domain.quark(), code, message, debug, filename, function, line)
    else:
      element.message_full(Gst.MessageType.WARNING, domain.quark(), code, message, debug, filename, function, line)

"""
  Gets an OAuth token for the given hostname, domain, username and password
"""
def get_oauth_token(hostname: str, domain: str, username: str, password: str) -> str | None:
  session = Session()
  session.mount("https://", SSLAdapter())
  session.verify = False # Highly unlikely we'll trust the Milestone cert, so just ignore errors

  # Check Oauth supported
  r = session.get("https://" + hostname + "/idp/.well-known/openid-configuration")
  if r.status_code != 200:
    return None

  body = r.json()

  if "server_version" not in body:
    return None

  # Check server version supports OAuth
  matches = re.findall(r"(\d+)\.(\d+)\.(\d+)", body["server_version"])
  if matches is None or int(matches[0][0]) < 21:
      return None

  token_endpoint = body["token_endpoint"]
  data = {
    "client_id": "GrantValidatorClient"
  }

  auth = None
  if domain == "BASIC":
    data.update({
      "grant_type": "password",
      "username": username,
      "password": password
    })
  else:
    data.update({
      "grant_type": "windows_credentials",
    })
    auth = HttpNtlmAuth(domain + "\\" + username, password)

  r = session.post(token_endpoint, auth=auth, data=data, headers={"Accept": "application/json"})
  if r.status_code != 200:
    return None

  return r.json()["access_token"]

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
        "recorder-host": (str,
                 "Recorder Host",
                 "IP Address of the Milestone XProtect Recorder server for this camera / hardware. Only use this if you need to override the recorder that the management server would usually return (i.e for DNS lookups not working correctly)",
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

    __gsignals__ = {
        'ptz': (GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION, None, (Gst.Structure,))
    }

    __gsttemplates__ = Gst.PadTemplate.new("src",
                                           Gst.PadDirection.SRC,
                                           Gst.PadPresence.ALWAYS,
                                           OCAPS)

    def __init__(self):
        GstBase.BaseSrc.__init__(self)

        self.management_server: str = ""
        self.recorder_host: str = ""
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

        self._recorder_service_client = None

    def do_get_property(self, prop):
        if prop.name == 'management-server':
            return self.management_server
        elif prop.name == 'recorder-host':
            return self.recorder_host
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
            raise AttributeError('Unable to get property %s' % prop.name)

    def do_set_property(self, prop, value):
        if prop.name == 'management-server':
            self.management_server = value
        elif prop.name == 'recorder-host':
            self.recorder_host = value
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
            raise AttributeError('Unable to set property %s to %s' % (prop.name, value))

    def do_start (self):
      if self.camera_id == "" and self.hardware_id != "":
        return False

      session = Session()
      session.mount("https://", SSLAdapter())
      session.verify = False # Highly unlikely we'll trust the Milestone cert, so just ignore errors
      urllib3.disable_warnings()

      # Try OAuth first
      oauth = get_oauth_token(self.management_server, self.user_domain, self.user_id, self.user_pw)

      if oauth is not None:
        Gst.info("Using OAuth token")
        session.headers.update({"Authorization": "Bearer " + oauth})
        url = "https://" + self.management_server + "/ManagementServer/ServerCommandServiceOAuth.svc?singleWsdl"
      else:
        Gst.info("Using standard auth")
        if self.user_domain == "BASIC":
          url = "https://" + self.management_server + "/ManagementServer/ServerCommandService.svc?wsdl"
          session.auth = auth.HTTPBasicAuth(username=self.user_id, password=self.user_pw)
        else:
          # TODO: This endpoint is marked as deprecated, but testing against a 2020R3 release doesn't work with the new endpoint?
          url = "http://" + self.management_server + "/ServerAPI/ServerCommandService.asmx?wsdl"
          session.auth = HttpNtlmAuth(self.user_domain + "\\" + self.user_id, self.user_pw)

      try:
        Gst.info("Instantiating SOAP Client")
        self.client = Client(url, transport=Transport(cache=SqliteCache(), session=session))
      except:
        element_message(self, Gst.CoreError, Gst.CoreError.STATE_CHANGE, "Error getting WSDL - likely an authentication failure")
        return False
      self.instance_id = str(uuid.uuid4())

      if self.force_management_address and "address" in self.client.service._binding_options:
        # Replace the hostname in the WSDL with the one we're using
        parsed = urlparse(self.client.service._binding_options["address"])
        self.client.service._binding_options["address"] = parsed._replace(netloc=self.management_server).geturl()

      self.service = self.client.service

      Gst.info("Performing login")
      login = self.service.Login(instanceId=self.instance_id)
      self.login_token: str = login.Token
      self.renew_time: datetime = login.RegistrationTime + timedelta(microseconds=login.TimeToLive.MicroSeconds) - timedelta(seconds=120)

      # If we've got the recorder host set, just use that
      if self.recorder_host != "":
        self.recorder_port = 7563
        self._recorder_tls = False
      else:
        # Work out which way we should obtain the recorder configuration
        # If we have the hardware ID, get it directly (and then set the camera-id if it was blank)
        if self.hardware_id != "":
          Gst.info("Have a hardware ID, so getting harware config directly")
          # array_of_guid = self.client.get_type('ns0:ArrayOfGuid')
          hardware_ids = {"guid": [self.hardware_id]}
          hardware_info = self.service.GetConfigurationHardware(login.Token, hardware_ids)
          if hardware_info is None or len(hardware_info) < 1:
            element_message(self, Gst.CoreError, Gst.CoreError.STATE_CHANGE, "Hardware ID not found")
            return False

          # Check the cameraId is mapped to the hardwareId
          if self.camera_id != "":
            if self.camera_id.lower() not in hardware_info[0].DeviceIds.guid:
              element_message(self, Gst.CoreError, Gst.CoreError.STATE_CHANGE, "Camera ID supplied not found for that Hardware ID")
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
            element_message(self, Gst.CoreError, Gst.CoreError.STATE_CHANGE, "Recorder for camera not found")
            return False

        recorder_result = urlparse(recorder_url)

        self._recorder_tls = recorder_result.scheme == "https"
        self.recorder_host = recorder_result.hostname
        self.recorder_port = recorder_result.port

      plain_sock = socket()
      if self._recorder_tls:
        self.socket = ssl_context.wrap_socket(plain_sock)
      else:
        self.socket = plain_sock

      if self.timeout != 0.0:
        self.socket.settimeout(self.timeout)
      try:
        Gst.info("Connecting to recording server (TLS: %s) %s:%d" % (self._recorder_tls, self.recorder_host, self.recorder_port))
        self.socket.connect((self.recorder_host, self.recorder_port))
      except:
        element_message(self, Gst.CoreError, Gst.CoreError.STATE_CHANGE, "Unable to connect to recording server")
        return False

      self.buffer = Buffer(self.socket)
      self.xmlGenerator = XmlGenerator(self.login_token, self.camera_id)

      # Send the initial connect to make sure we're good to go
      self.socket.sendall(bytes(self.xmlGenerator.connect(), 'UTF-8'))
      self.socket.sendall(b'\r\n\r\n')

      try:
        response = self.buffer.get_line()
      except:
        element_message(self, Gst.CoreError, Gst.CoreError.STATE_CHANGE, "Error getting initial connect response")
        return False
      root = ET.fromstring(response)
      elem = root.find('connected')
      if elem is None or elem.text != 'yes':
        element_message(self, Gst.CoreError, Gst.CoreError.STATE_CHANGE, "Unable to send start command to recording server")
        return False

      Gst.info("Recording server connected")

      return True

    def renew_token(self):
      try:
        Gst.info("Renewing token")
        login = self.service.Login(instanceId=self.instance_id, currentToken=self.login_token)
        self.login_token = login.Token
        self.renew_time: datetime = login.RegistrationTime + timedelta(microseconds=login.TimeToLive.MicroSeconds) - timedelta(seconds=60)
        self.socket.sendall(bytes(self.xmlGenerator.connect_update(), 'UTF-8'))
        self.socket.sendall(b'\r\n\r\n')
      except:
        raise

    # This method is called by gstreamer to create a buffer
    # We don't use the args
    def do_create(self, *args):
      if self.started == False:
        Gst.info("Sending start live command")
        self.socket.sendall(bytes(self.xmlGenerator.live(), 'UTF-8'))
        self.socket.sendall(b'\r\n\r\n')
        self.started = True

      while True:
        if self.renew_time < datetime.now(UTC):
          Gst.info("Renewing token with management server")
          try:
            self.renew_token()
          except:
            element_message(self, Gst.ResourceError, Gst.ResourceError.READ, "Error renewing token")
            break

        try:
          response = self.buffer.get_line()
        except Exception as inst:
          element_message(self, Gst.ResourceError, Gst.ResourceError.READ, "Error getting data from recording server")
          return (Gst.FlowReturn.EOS, None)
        # Socket closed, return with an EOS
        if response is None:
          element_message(self, Gst.ResourceError, Gst.ResourceError.READ, "Socket with recording server closed")
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
            try:
              mbytes = self.buffer.get_buffer_size(size)
            except:
              element_message(self, Gst.ResourceError, Gst.ResourceError.READ, "Error getting buffer of fixed size")
              break
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
                    message = "connectupdate failed %s" % response
                    element_message(self, Gst.ResourceError, Gst.ResourceError.READ, message, response)
                    break

                message = "Unknown methodresponse - %s" % response
                element_message(self, Gst.ResourceError, Gst.ResourceError.READ, message, response, "warning")
                continue

            except:
              message = "Error decoding XML - %s" % response
              element_message(self, Gst.ResourceError, Gst.ResourceError.READ, message, response)
              break

          else:
            if response == "":
              continue

            message = "Unknown response %s" % str(response)
            element_message(self, Gst.ResourceError, Gst.ResourceError.READ, message, response, "warning")

            continue

        except Exception as inst:
          message = "Unknown exception encountered - %s" % type(inst).__name__
          element_message(self, Gst.ResourceError, Gst.ResourceError.READ, message)
          break

      return (Gst.FlowReturn.ERROR, None)

    def do_ptz(self, data):
      """
        Virtual method called by GObject action signal to send a PTZ command
        Establishes the service channel with the recorder if it hasn't already been done
      """

      if not self.started:
        return

      if data.get_name() != 'PTZCommand' or not data.has_field("x") or not data.has_field("y") or not data.has_field("z"):
        return

      x = data.get_value("x")
      y = data.get_value("y")
      z = data.get_value("z")

      if self._recorder_service_client is None:
        self._setup_recorder_service_client()

      try:
        Gst.info("Sending PTZ command")
        # Build PTZ Args
        if x == 0 and y == 0 and z == 0:
          self._recorder_service_client.service.PTZMoveStop(token=self.login_token, deviceId=self.camera_id)
          return

        if x != 0 or y != 0:
          pan = 0
          tilt = 0

          if x > 0:
            pan = 1
          elif x < 0:
            pan = -1

          if y > 0:
            tilt = 1
          elif y < 0:
            tilt = -1

          ptz_args = {
            "movement": [
              {"name": "pan", "value": pan},
              {"name": "tilt", "value": tilt},
            ],
            "speed": [
              {"name": "pan", "value": abs(x)},
              {"name": "tilt", "value": abs(y)}
            ],
            "Normalized": False
          }
          self._recorder_service_client.service.PTZMoveStart(token=self.login_token, deviceId=self.camera_id, ptzArgs=ptz_args)
          return

        if z != 0:
          zoom = 0
          if z > 0:
            zoom = 1
          elif z < 0:
            zoom = -1
          ptz_args = {
            "movement": [
              {"name": "zoom", "value": zoom},
            ],
            "speed": [
              {"name": "zoom", "value": abs(z)},
            ],
            "Normalized": False
          }

          self._recorder_service_client.service.PTZMoveStart(token=self.login_token, deviceId=self.camera_id, ptzArgs=ptz_args)
      except Exception as e:
        Gst.warning("Error sending PTZ command - %s" % str(e))
        return

    def _setup_recorder_service_client(self):
      """
        Sets up the SOAP client to talk to the recorder service
      """

      if self._recorder_service_client is not None:
        return

      session = Session()
      session.mount("https://", SSLAdapter())
      session.verify = False # Highly unlikely we'll trust the Milestone cert, so just ignore errors
      urllib3.disable_warnings()

      if self._recorder_tls:
        url = "https://" + self.recorder_host + ":" + str(self.recorder_port) + "/RecorderCommandService/RecorderCommandService.asmx?wsdl"
      else:
        url = "http://" + self.recorder_host + ":" + str(self.recorder_port) + "/RecorderCommandService/RecorderCommandService.asmx?wsdl"

      self._recorder_service_client = Client(url, transport=Transport(cache=SqliteCache(), session=session))
      # We have to tell zeep to strip the ns0 prefix from the SOAP Envelope, otherwise Milestone doesn't decode it properly
      for ns in self._recorder_service_client.namespaces:
        if "videoos" in self._recorder_service_client.namespaces[ns]:
          self._recorder_service_client.set_ns_prefix(None, self._recorder_service_client.namespaces[ns])
          break


__gstelementfactory__ = ("milestonexprotectsrc", Gst.Rank.NONE, MilestoneXprotectSrc)