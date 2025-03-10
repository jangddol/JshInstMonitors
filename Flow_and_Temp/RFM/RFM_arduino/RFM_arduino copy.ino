int flowSetpointBuffer = 0;
char MeasureBuffer[17];

// pc specific
const int PC_INPUT_MAX = 200;

// arduino specific
#ifdef ARDUINO_ARCH_SAM
const int ARDUINO_WRITE_MAX = 4095;
#else
const int ARDUINO_WRITE_MAX = 255;
#endif
#if defined(ARDUINO_ARCH_SAM) || defined(ARDUINO_SAMD_ZERO) || defined(ESP32)
const int ARDUINO_READ_MAX = 4095; // 12비트 최대 값
#else
const int ARDUINO_READ_MAX = 1023; // 10비트 최대 값
#endif

const int NUM_CHANNELS = 4;

// COMMAND list
const char FLOW_STATE_COMMANDS_HIGH[NUM_CHANNELS] = {'a', 's', 'd', 'f'};
const char FLOW_STATE_COMMANDS_LOW[NUM_CHANNELS] = {'z', 'x', 'c', 'v'};
const char FLOW_SETPOINT_COMMANDS[NUM_CHANNELS] = {'q', 'w', 'e', 'r'};
const char NUMBER_COMMANDS[10] = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'};
const char RESET_COMMAND = 'B';

// pin assignment
const int FLOW_STATE_CH[NUM_CHANNELS] = {2, 7, 8, 13};
const int FLOW_SETPOINT_CH[NUM_CHANNELS] = {3, 5, 9, 11};
const int FLOW_MEAS_CH[NUM_CHANNELS] = {A0, A1, A2, A3};

void resetMeasureBuffer()
{
    memset(MeasureBuffer, '0', 16); // MeasureBuffer의 처음 16바이트를 '0'으로 설정
    MeasureBuffer[16] = '\0';       // null 종료 문자 추가
}

int getIndexInArray(const char arr[], int size, int element)
{
    for (int i = 0; i < size; i++)
    {
        if (arr[i] == element)
        {
            return i;
        }
    }
    return -1;
}

bool isInArray(const char arr[], int size, int element)
{
    return getIndexInArray(arr, size, element) != -1;
}

// 4개의 4자리 정수를 16자리 문자열로 포맷하는 함수
void formatNumbersTo16Chars(int *values, char *result)
{
    // 각 정수를 4자리로 포맷하여 result에 저장
    snprintf(result, 16, "%04d%04d%04d%04d", values[0], values[1], values[2], values[3]);
}

void updateMeasureBuffer()
{
    int values[NUM_CHANNELS] = {0, 0, 0, 0};
    for (int i = 0; i < NUM_CHANNELS; i++)
    {
        values[i] = analogRead(FLOW_MEAS_CH[i]);
        values[i] = values[i] % 10000; // Ensure values are 4 digit decimal numbers
    }

    formatNumbersTo16Chars(values, MeasureBuffer);
}

void writeFlowState(char command)
{
    if (isInArray(FLOW_STATE_COMMANDS_HIGH, NUM_CHANNELS, command))
    {
        int chIndex = getIndexInArray(FLOW_STATE_COMMANDS_HIGH, NUM_CHANNELS, command);
        digitalWrite(FLOW_STATE_CH[chIndex], HIGH);
    }
    if (isInArray(FLOW_STATE_COMMANDS_LOW, NUM_CHANNELS, command))
    {
        int chIndex = getIndexInArray(FLOW_STATE_COMMANDS_LOW, NUM_CHANNELS, command);
        analogWrite(FLOW_STATE_CH[chIndex], LOW);
    }
}

void writeFlowSetpointSetting(char command)
{
    int channelIndex = getIndexInArray(FLOW_SETPOINT_COMMANDS, NUM_CHANNELS, command);
    if (channelIndex == -1)
        return;

    int value = map(flowSetpointBuffer, 0, PC_INPUT_MAX, 0, ARDUINO_WRITE_MAX);
    analogWrite(FLOW_SETPOINT_CH[channelIndex], value);
    flowSetpointBuffer = 0;
}

void pinAssignment()
{
    for (int i = 0; i < NUM_CHANNELS; i++)
    {
        pinMode(FLOW_STATE_CH[i], OUTPUT);
        pinMode(FLOW_SETPOINT_CH[i], OUTPUT);
        pinMode(FLOW_MEAS_CH[i], INPUT);
    }
}

void reset()
{
    for (int i = 0; i < NUM_CHANNELS; i++)
    {
        digitalWrite(FLOW_STATE_CH[i], HIGH);
        analogWrite(FLOW_SETPOINT_CH[i], 0);
    }
    resetMeasureBuffer();
}

void setup()
{
    Serial.begin(9600);
#ifdef ARDUINO_ARCH_SAM
    analogWriteResolution(12);
#endif
#if defined(ARDUINO_ARCH_SAM) || defined(ARDUINO_SAMD_ZERO) || defined(ESP32)
    analogReadResolution(12);
#endif
    pinAssignment();
    reset();
}

void loop()
{
    while (Serial.available())
    {
        char serialBuffer = Serial.read();

        if (isInArray(FLOW_STATE_COMMANDS_HIGH, NUM_CHANNELS, serialBuffer) || isInArray(FLOW_STATE_COMMANDS_LOW, NUM_CHANNELS, serialBuffer))
        {
            writeFlowState(serialBuffer);
        }
        else if (isInArray(NUMBER_COMMANDS, 10, serialBuffer))
        {
            flowSetpointBuffer = 10 * flowSetpointBuffer + serialBuffer - '0';
        }
        else if (isInArray(FLOW_SETPOINT_COMMANDS, NUM_CHANNELS, serialBuffer))
        {
            writeFlowSetpointSetting(serialBuffer);
        }
        else if (serialBuffer == RESET_COMMAND)
        {
            reset();
        }
    }

    updateMeasureBuffer();
    Serial.println(MeasureBuffer);
    delay(10);
}