from datetime import datetime, timedelta
from requests import auth, Session
from requests_ntlm import HttpNtlmAuth
from socket import *
from urllib.parse import urlparse
import uuid
import urllib3
import logging
import sys
from zeep import Client
from zeep.cache import SqliteCache
from zeep.transports import Transport

# Logging
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel("INFO")
logger.addHandler(handler)

class MilestoneDiscovery:
  def __init__(self, user_id, user_pw, domain, management_server, force_management_address=False):
    self.domain = domain
    self.force_management_address = force_management_address
    self.management_server = management_server
    self.user_pw = user_pw
    self.user_id = user_id

    session = Session()
    if self.domain == "BASIC":
      url = "https://" + self.management_server + "/ManagementServer/ServerCommandService.svc"
      session.auth = auth.HTTPBasicAuth(username=self.user_id, password=self.user_pw)
      session.verify = False # Highly unlikely we'll trust the Milestone cert, so just ignore errors
      urllib3.disable_warnings()
      binding_override_namespace = "{http://tempuri.org/}BasicHttpBinding_IServerCommandService"
    else:
      # TODO: This endpoint is marked as deprecated, but testing against a 2020R3 release doesn't work with the new endpoint?
      url = "http://" + self.management_server + "/ServerAPI/ServerCommandService.asmx"
      session.auth = HttpNtlmAuth(self.domain + "\\" + self.user_id, self.user_pw)
      binding_override_namespace = "{http://videoos.net/2/XProtectCSServerCommand}ServerCommandServiceSoap"

    try:
      logger.info("Instantiating SOAP Client")
      self.client = Client(url + "?wsdl", transport=Transport(cache=SqliteCache(), session=session))
    except:
      return logger.error()
    self.instance_id = str(uuid.uuid4())

    if self.force_management_address:
      self.service = self.client.create_service(binding_override_namespace, url)
    else:
      self.service = self.client.service

    logger.info("Performing login")
    login = self.service.Login(instanceId=self.instance_id)
    self.login_token: str = login.Token
    self.renew_time: datetime = login.RegistrationTime + timedelta(microseconds=login.TimeToLive.MicroSeconds) - timedelta(seconds=60)

    logger.info("Getting whole site configuration")
    self.config = self.service.GetConfiguration(token=login.Token)
    logger.info("Got site config")

    camera_count = 0
    recorder_count = 0
    for recorder in self.config.Recorders.RecorderInfo:
      print(recorder)
      recorder_count += 1
      for camera in recorder.Cameras.CameraInfo:
        camera_count += 1

    logger.info("Found %d cameras across %d recorders" % (camera_count, recorder_count))

  def get_camera_details(self):
    cameras = []
    for recorder in self.config.Recorders.RecorderInfo:
      for camera in recorder.Cameras.CameraInfo:
        camera_info = {
          "name": camera.Name,
          "url": "milestone://" + self.domain + "\\" + self.user_id + ":" + self.user_pw + "@" + self.management_server + "/?cameraId=" + camera.DeviceId + "&hardwareId=" + camera.HardwareId,
          "recorder": recorder.WebServerUri
        }
        cameras.append(camera_info)
    print(cameras)

milestone = MilestoneDiscovery(user_id="basic", user_pw="basic", domain="BASIC", management_server="192.168.1.100")
milestone.get_camera_details()
