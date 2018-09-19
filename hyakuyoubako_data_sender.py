#!/usr/bin/env python
# -*- coding: utf-8 -*-

#HYAKUYOBAKO DATA SENDER


"""
"""

from smbus import SMBus

import argparse
import base64
import datetime
import json
import threading
import time

import jwt
import requests


_BASE_URL = 'https://cloudiotdevice.googleapis.com/v1'
bus_number  = 1
i2c_address = 0x76

bus = SMBus(bus_number)

digT = []
digP = []
digH = []

t_fine = 0.0

resending_status = False 

class ResendThread(threading.Thread):

    def __init__(self, args, jwt_token, jwt_iat, jwt_exp_mins):
        super(ResendThread, self).__init__()
        self.args = args
        self.jwt_token = jwt_token
        self.jwt_iat = jwt_iat
        self.jwt_exp_mins = jwt_exp_mins
        
    def run(self):
        global resending_status
        if resending_status:
            return


	resending_status = True
        
        file = ng_message_file = open('send_ng_message.txt','r')
        messages = file.readlines()
        file.close()
        for message in messages:
            seconds_since_issue = (datetime.datetime.utcnow() - self.jwt_iat).seconds
            if seconds_since_issue > 60 * self.jwt_exp_mins:
                print('Refreshing token after {}s').format(seconds_since_issue)
                self.jwt_token = create_jwt(
                        self.args.project_id, self.args.private_key_file, self.args.algorithm)
                self.jwt_iat = datetime.datetime.utcnow()

            print('RePublishing message : \'{}\''.format(message))

            resp = publish_message(
                    message, self.args.message_type, self.args.base_url, self.args.project_id,
                    self.args.cloud_region, self.args.registry_id, self.args.device_id, self.jwt_token)

            #On HTTP error , write message to file.
            if resp.status_code != requests.codes.ok:
                ng_message_file = open('send_ng_message.txt','a')
                ng_message_file.write(message_data)
                ng_message_file.write('\n')
                ng_message_file.close()
            else:
                #call resend process
                print 'else'
            print('HTTP response: ', resp) 
        resending_status = False

def writeReg(reg_address, data):
        bus.write_byte_data(i2c_address,reg_address,data)

def get_calib_param():
        calib = []

        for i in range (0x88,0x88+24):
                calib.append(bus.read_byte_data(i2c_address,i))
        calib.append(bus.read_byte_data(i2c_address,0xA1))
        for i in range (0xE1,0xE1+7):
                calib.append(bus.read_byte_data(i2c_address,i))

        digT.append((calib[1] << 8) | calib[0])
        digT.append((calib[3] << 8) | calib[2])
        digT.append((calib[5] << 8) | calib[4])
        digP.append((calib[7] << 8) | calib[6])
        digP.append((calib[9] << 8) | calib[8])
        digP.append((calib[11]<< 8) | calib[10])
        digP.append((calib[13]<< 8) | calib[12])
        digP.append((calib[15]<< 8) | calib[14])
        digP.append((calib[17]<< 8) | calib[16])
        digP.append((calib[19]<< 8) | calib[18])
        digP.append((calib[21]<< 8) | calib[20])
        digP.append((calib[23]<< 8) | calib[22])
        digH.append( calib[24] )
        digH.append((calib[26]<< 8) | calib[25])
        digH.append( calib[27] )
        digH.append((calib[28]<< 4) | (0x0F & calib[29]))
        digH.append((calib[30]<< 4) | ((calib[29] >> 4) & 0x0F))
        digH.append( calib[31] )

        for i in range(1,2):
                if digT[i] & 0x8000:
                        digT[i] = (-digT[i] ^ 0xFFFF) + 1

        for i in range(1,8):
                if digP[i] & 0x8000:
                        digP[i] = (-digP[i] ^ 0xFFFF) + 1

        for i in range(0,6):
                if digH[i] & 0x8000:
                        digH[i] = (-digH[i] ^ 0xFFFF) + 1

def setup():
        osrs_t = 1                      #Temperature oversampling x 1
        osrs_p = 1                      #Pressure oversampling x 1
        osrs_h = 1                      #Humidity oversampling x 1
        mode   = 3                      #Normal mode
        t_sb   = 5                      #Tstandby 1000ms
        filter = 0                      #Filter off
        spi3w_en = 0                    #3-wire SPI Disable

        ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | mode
        config_reg    = (t_sb << 5) | (filter << 2) | spi3w_en
        ctrl_hum_reg  = osrs_h

        writeReg(0xF2,ctrl_hum_reg)
        writeReg(0xF4,ctrl_meas_reg)
        writeReg(0xF5,config_reg)


def compensate_P(adc_P):
        global  t_fine
        pressure = 0.0

        v1 = (t_fine / 2.0) - 64000.0
        v2 = (((v1 / 4.0) * (v1 / 4.0)) / 2048) * digP[5]
        v2 = v2 + ((v1 * digP[4]) * 2.0)
        v2 = (v2 / 4.0) + (digP[3] * 65536.0)
        v1 = (((digP[2] * (((v1 / 4.0) * (v1 / 4.0)) / 8192)) / 8)  + ((digP[1] * v1) / 2.0)) / 262144
        v1 = ((32768 + v1) * digP[0]) / 32768

        if v1 == 0:
                return 0
        pressure = ((1048576 - adc_P) - (v2 / 4096)) * 3125
        if pressure < 0x80000000:
                pressure = (pressure * 2.0) / v1
        else:
                pressure = (pressure / v1) * 2
        v1 = (digP[8] * (((pressure / 8.0) * (pressure / 8.0)) / 8192.0)) / 4096
        v2 = ((pressure / 4.0) * digP[7]) / 8192.0
        pressure = pressure + ((v1 + v2 + digP[6]) / 16.0)


        return (pressure / 100)

def compensate_T(adc_T):
        global t_fine
        v1 = (adc_T / 16384.0 - digT[0] / 1024.0) * digT[1]
        v2 = (adc_T / 131072.0 - digT[0] / 8192.0) * (adc_T / 131072.0 - digT[0] / 8192.0) * digT[2]
        t_fine = v1 + v2
        temperature = t_fine / 5120.0
        #print "temp : %-6.2f  % (temperature)
        return temperature	

def compensate_H(adc_H):
        global t_fine
        var_h = t_fine - 76800.0
        if var_h != 0:
                var_h = (adc_H - (digH[3] * 64.0 + digH[4]/16384.0 * var_h)) *\
                    (digH[1] / 65536.0 * (1.0 + digH[5] / 67108864.0 * var_h *\
                        (1.0 + digH[2] / 67108864.0 * var_h)))
        else:
                return 0
        var_h = var_h * (1.0 - digH[0] * var_h / 524288.0)
        if var_h > 100.0:
                var_h = 100.0
        elif var_h < 0.0:
                var_h = 0.0
        #print "hum : %6.2f " % (var_h)
        return var_h

def readData():
        data = []
        for i in range (0xF7, 0xF7+8):
                data.append(bus.read_byte_data(i2c_address,i))
        pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        hum_raw  = (data[6] << 8)  |  data[7]
        

        datas = {'temperature':compensate_T(temp_raw) ,\
                'pressure':compensate_P(pres_raw), 'humidity':compensate_H(hum_raw)}
 
        return datas
       
def create_message(id, logitude, latitude):
    datas = readData()

    #送信するメッセージをJSON形式にする
    message = '{{\
        "ID":"{}",\
        "LOCATION_LOGI":"{}",\
        "LOCATION_LATI":"{}",\
        "DEVICE_DATETIME":"{}",\
        "TEMPERATURE":"{}",\
        "PRESSURE":"{}",\
        "HUMIDITY":"{}"}}'.format(id, logitude, latitude, datetime.datetime.now().\
            strftime('%Y-%m-%d %H:%M:%S'),datas['temperature'] ,datas['pressure'] ,datas['humidity'])
    return message


def create_jwt(project_id, private_key_file, algorithm):
    token = {
            # The time the token was issued.
            'iat': datetime.datetime.utcnow(),
            # Token expiration time.
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60),
            # The audience field should always be set to the GCP project id.
            'aud': project_id
    }

    # Read the private key file.
    with open(private_key_file, 'r') as f:
        private_key = f.read()

    #print('Creating JWT using {} from private key file {}'.format(
    #        algorithm, private_key_file))

    return jwt.encode(token, private_key, algorithm=algorithm)


def publish_message(
        message, message_type, base_url, project_id, cloud_region, registry_id,
        device_id, jwt_token):
    headers = {
            'authorization': 'Bearer {}'.format(jwt_token),
            'content-type': 'application/json',
            'cache-control': 'no-cache'
    }

    # Publish to the events or state topic based on the flag.
    url_suffix = 'publishEvent' if message_type == 'event' else 'setState'

    publish_url = (
        '{}/projects/{}/locations/{}/registries/{}/devices/{}:{}').format(
            base_url, project_id, cloud_region, registry_id, device_id,
            url_suffix)

    #print('Publishing URL : \'{}\''.format(publish_url))

    body = None
    if message_type == 'event':
        body = {'binary_data': base64.urlsafe_b64encode(message)}
    else:
        body = {
          'state': {'binary_data': base64.urlsafe_b64encode(message)}
        }

    resp = requests.post(
            publish_url, data=json.dumps(body),  headers=headers)

    return resp


def parse_command_line_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=(
            'HYAKUYOBAKO Data sender.'))
    parser.add_argument(
            '--project_id', required=True, help='GCP cloud project name')
    parser.add_argument(
            '--registry_id', required=True, help='Cloud IoT Core registry id')
    parser.add_argument(
            '--device_id', required=True, help='Cloud IoT Core device id')
    parser.add_argument(
            '--private_key_file',
            required=True,
            help='Path to private key file.')
    parser.add_argument(
            '--algorithm',
            choices=('RS256', 'ES256'),
            required=True,
            help='The encryption algorithm to use to generate the JWT.')
    parser.add_argument(
            '--cloud_region', default='us-central1', help='GCP cloud region')
    parser.add_argument(
            '--ca_certs',
            default='roots.pem',
            help=('CA root from https://pki.google.com/roots.pem'))
    parser.add_argument(
            '--message_type',
            choices=('event', 'state'),
            default='event',
            required=True,
            help=('Indicates whether the message to be published is a '
                  'telemetry event or a device state message.'))
    parser.add_argument(
            '--base_url',
            default=_BASE_URL,
            help=('Base URL for the Cloud IoT Core Device Service API'))
    parser.add_argument(
            '--jwt_expires_minutes',
            default=20,
            type=int,
            help=('Expiration time, in minutes, for JWT tokens.'))
    parser.add_argument(
            '--id',
            default=999,
            type=int,
            help=('Device id, not IoT Core device id for unique key.'))
    parser.add_argument(
            '--location_logitude',
            default=0.0,
            type=float,
            help=('Logitude of this deice. ex)35.658581'))
    parser.add_argument(
            '--location_latitude',
            default=0.0,
            type=float,
            help=('Latitude of this deice. ex)139.745433'))

    return parser.parse_args()


def send_message(args, jwt_token, jwt_iat, jwt_exp_mins):
        seconds_since_issue = (datetime.datetime.utcnow() - jwt_iat).seconds
        if seconds_since_issue > 60 * jwt_exp_mins:
            #print('Refreshing token after {}s').format(seconds_since_issue)
            jwt_token = create_jwt(
                args.project_id, args.private_key_file, args.algorithm)
            jwt_iat = datetime.datetime.utcnow()

        message_data = create_message(args.id, args.location_logitude, args.location_latitude)

        #print('Publishing message : \'{}\''.format(message_data))
        
        try: 
            resp = publish_message(
                   message_data, args.message_type, args.base_url, args.project_id,
                   args.cloud_region, args.registry_id, args.device_id, jwt_token)
        except:
            print 'Message send error'

        
        #On HTTP error , write datas to csv file.
        if (resp is None) or (resp.status_code != requests.codes.ok):
            datas = json.loads(message_data)
            #送信に失敗した場合、send_ng_message.txtファイルに送れなかったメッセージを書き込む。
            ng_message_file = open('send_ng_message.txt','a')
            ng_message_file.write(datas['ID'])
            ng_message_file.write(',')
            ng_message_file.write(datas['LOCATION_LOGI'])
            ng_message_file.write(',')
            ng_message_file.write(datas['LOCATION_LATI'])
            ng_message_file.write(',')
            ng_message_file.write(datas['DEVICE_DATETIME'])
            ng_message_file.write(',')
            ng_message_file.write(datas['TEMPERATURE'])
            ng_message_file.write(',')
            ng_message_file.write(datas['PRESSURE'])
            ng_message_file.write(',')
            ng_message_file.write(datas['HUMIDITY'])

            ng_message_file.write('\n')
            ng_message_file.close()
        #正常に送信出来た際、送信できなかったメッセージを再送信する処理。
        #else: 
            #call resend process
        #    resend_thread = ResendThread(args, jwt_token, jwt_iat, jwt_exp_mins)
        #    resend_thread.start()
            
        #print('HTTP response: ', resp)


def main():
    args = parse_command_line_args()

    jwt_token = create_jwt(
            args.project_id, args.private_key_file, args.algorithm)
    jwt_iat = datetime.datetime.utcnow()
    jwt_exp_mins = args.jwt_expires_minutes

    # Publish mesages to the HTTP bridge once per minite.
    while True:
   
        send_message(args, jwt_token, jwt_iat, jwt_exp_mins)
       
        #5分に一度データを送信する
        time.sleep(300 if args.message_type == 'event' else 5)
    #print('Finished.')


#Setup for BME280
setup()
get_calib_param()

if __name__ == '__main__':
    main()

