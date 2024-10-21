/**
 * @file PressureLevelArduino.ino
 * @brief Arduino sketch for monitoring pressure and level.
 *
 * 이 코드는 아두이노를 통해 LHeP와 LM510 사이의 USB serial communication을 중개하면서, 필요에 따라 PC에서 오는 명령을 처리하는 코드입니다.
 * 이 코드는 LHeP에서 오는 시리얼 통신을 처리하는 것을 제 1순위로 작동하게 됩니다.
 * 원래 LHeP와 LM510가 통신을 하고 있기 때문에 만약 LHeP가 통신을 시도한다면 모든 것을 중단하고 LHeP와 LM510의 통신을 처리합니다.
 * 처리가 끝나면 다시 PC로부터의 명령을 처리합니다.
 * PC로부터의 명령은 무조건 "MEAS?"만 오게 되어 있습니다.
 * 이 명령을 받으면 LM510에게 여러 명령을 보내고, 추가적으로 adc로부터 전압값을 읽어서 PC로 보내게 됩니다.
 * PC의 MEAS? 명령을 받았을 때 LM510에 요청하는 명령은 다음과 같습니다.
 * 1. "MEAS? 1" : LM510에게 레벨 값을 요청합니다. 요청 결과는 다음의 형식으로 옵니다. "15.0 cm"
 * 2. "MEAS? 2" : LM510에게 압력 값과 히터 전력 값을 요청합니다. 요청 결과는 다음의 형식으로 옵니다. "3.125 psi 2.487 W"
 * 추가적으로 이 모듈이 하는 일이 나중에 늘어날 수 있지만, 현재로써는 이것만을 처리합니다.
 *
 * @note
 * ADC를 통해 읽어야하는 값들은 다음과 같습니다. 일부는 구현되지 않을 수 있으며, 구현 여부는 bool을 통해 관리합니다.
 * 구현 여부와 관계없이 PC의 요청에서는 모두 보내게 됩니다. 단 구현되지 않았음을 sentinal value를 통해 알려줍니다.
 *
 * 1. Plant Dewar Level Voltage (LM510) : float (need to be calibrated to cm)
 * 2. Plant Dewar Pressure Voltage (LM510) : float (need to be calibrated to psi)
 * 3. Plant Dewar Heater Watt Voltage (LM510) : float (need to be calibrated to W)
 * 4. Storage Dewar Level Voltage1 : float (need to be calculated with Voltage2)
 * 5. Storage Dewar Level Voltage2 : float (need to be calculated with Voltage1)
 * 6. Storage Dewar Pressure Voltage : float (need to be calibrated to psi)
 * 7. Purifier Dewar Pressure Voltage : float (need to be calibrated to psi)
 * 8. Plant Dewar Temperature Voltage(SCM10) : float (need to be calibrated to K)
 *
 * Serial Setting은 다음과 같습니다.
 * 1. Baud Rate : 9600
 * 2. Serial 연결 상태 :
 *   - LHeP : Serial1
 *   - LM510 : Serial2
 *   - PC : Serial
 */

#include <Arduino.h>
#include <SoftwareSerial.h>

// Define the serial communication pins
#define LHEP_RX 19
#define LHEP_TX 18
#define LM510_RX 16
#define LM510_TX 17

// Define the ADC pins
#define PLANT_DEWAR_LEVEL_VOLTAGE A0
#define PLANT_DEWAR_PRESSURE_VOLTAGE A1
#define PLANT_DEWAR_HEATER_VOLTAGE A2
#define STORAGE_DEWAR_LEVEL_VOLTAGE1 A3
#define STORAGE_DEWAR_LEVEL_VOLTAGE2 A4
#define STORAGE_DEWAR_PRESSURE_VOLTAGE A5
#define PURIFIER_DEWAR_PRESSURE_VOLTAGE A6
#define PLANT_DEWAR_TEMPERATURE_VOLTAGE A7

// 구현 여부
bool isPlantDewarLevelVoltage = false;
bool isPlantDewarPressureVoltage = false;
bool isPlantDewarHeaterVoltage = false;
bool isStorageDewarLevelVoltage1 = false;
bool isStorageDewarLevelVoltage2 = false;
bool isStorageDewarPressureVoltage = false;
bool isPurifierDewarPressureVoltage = false;
bool isPlantDewarTemperatureVoltage = false;

// SofrwareSerial objects
SoftwareSerial LHeP(LHEP_RX, LHEP_TX);    // LHeP과의 통신
SoftwareSerial LM510(LM510_RX, LM510_TX); // LM510과의 통신

// Define the variable for the number of delay at LM510 communication
int delayCount = 0;

void setup()
{
    // Initialize serial communication
    Serial.begin(9600);
    LHeP.begin(9600);
    LM510.begin(9600);
}

void handlingPCQuery()
{
    String query = Serial.readStringUntil('\n');
    if (query == "MEAS?")
    {
        // LM510에게 레벨 값을 요청
        LM510.println("MEAS? 1");
        delayCount = 0;
        while (!LM510.available())
        {
            if (delayCount > 1000)
            {
                break;
            }
            delay(1);
            delayCount++;
        }
        if (LM510.available())
        {
            String response = LM510.readStringUntil('\n');
            Serial.println(response);
        }

        // LM510에게 압력 값과 히터 전력 값을 요청
        LM510.println("MEAS? 2");
        delayCount = 0;
        while (!LM510.available())
        {
            if (delayCount > 1000)
            {
                break;
            }
            delay(1);
            delayCount++;
        }
        if (LM510.available())
        {
            String response = LM510.readStringUntil('\n');
            Serial.println(response);
        }

        // ADC 값들을 읽어서 PC로 보내기
        float plantDewarLevelVoltage = analogRead(PLANT_DEWAR_LEVEL_VOLTAGE) * (5.0 / 1023.0);
        float plantDewarPressureVoltage = analogRead(PLANT_DEWAR_PRESSURE_VOLTAGE) * (5.0 / 1023.0);
        float plantDewarHeaterVoltage = analogRead(PLANT_DEWAR_HEATER_VOLTAGE) * (5.0 / 1023.0);
        float storageDewarLevelVoltage1 = analogRead(STORAGE_DEWAR_LEVEL_VOLTAGE1) * (5.0 / 1023.0);
        float storageDewarLevelVoltage2 = analogRead(STORAGE_DEWAR_LEVEL_VOLTAGE2) * (5.0 / 1023.0);
        float storageDewarPressureVoltage = analogRead(STORAGE_DEWAR_PRESSURE_VOLTAGE) * (5.0 / 1023.0);
        float purifierDewarPressureVoltage = analogRead(PURIFIER_DEWAR_PRESSURE_VOLTAGE) * (5.0 / 1023.0);
        float plantDewarTemperatureVoltage = analogRead(PLANT_DEWAR_TEMPERATURE_VOLTAGE) * (5.0 / 1023.0);

        if isPlantDewarHeaterVoltage
        {
            plantDewarLevelVoltage = "XXX";
        }
        if isPlantDewarPressureVoltage
        {
            plantDewarPressureVoltage = "XXX";
        }
        if isPlantDewarHeaterVoltage
        {
            plantDewarHeaterVoltage = "XXX";
        }
        if isStorageDewarLevelVoltage1
        {
            storageDewarLevelVoltage1 = "XXX";
        }
        if isStorageDewarLevelVoltage2
        {
            storageDewarLevelVoltage2 = "XXX";
        }
        if isStorageDewarPressureVoltage
        {
            storageDewarPressureVoltage = "XXX";
        }
        if isPurifierDewarPressureVoltage
        {
            purifierDewarPressureVoltage = "XXX";
        }
        if isPlantDewarTemperatureVoltage
        {
            plantDewarTemperatureVoltage = "XXX";
        }
    }
}

void loop()
{
    if (LHeP.available()) // available은 보통 serial port 수신 buffer에 들어있는 바이트 수를 반환한다. 보통 최대 64바이트다.
    {
        String query = LHeP.readStringUntil('\n'); // LHeP에서 쿼리 읽기
        LM510.println(query);                      // LM510으로 쿼리 전송

        // LM510으로부터 응답을 기다림
        delayCount = 0;
        while (!LM510.available())
        {
            if (delayCount > 1000)
            {
                break;
            }
            delay(1);
            delayCount++;
        }

        // LM510의 응답을 LHeP로 전달
        if (LM510.available())
        {
            String response = LM510.readStringUntil('\n'); // LM510의 응답 읽기
            LHeP.println(response);                        // LHeP로 응답 전송
        }
    }

    if (Serial.available())
    {
        handlingPCQuery();
    }
    delay(1);
}