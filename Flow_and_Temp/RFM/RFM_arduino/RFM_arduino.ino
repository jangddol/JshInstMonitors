int flowSetpointBuffer = 0;
float MeasureBuffer = 0.000;

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
const char MEASCHPAIR_COMMANDS[24] = {'t', 'y', 'u', 'i', 'o', 'p', 'g', 'h', 'j', 'k', 'l', 'b', 'n', 'm', 'Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'};
const char RESET_COMMAND = 'B';

struct MeasChPair
{
    int firstCh;
    int secondCh;
};

const MeasChPair measChPairMap[24] = {
    {1, -1}, {1, 1}, {1, 2}, {1, 3}, {1, 4}, {2, -1}, {2, 1}, {2, 2}, {2, 3}, {2, 4}, {3, -1}, {3, 1}, {3, 2}, {3, 3}, {3, 4}, {4, -1}, {4, 1}, {4, 2}, {4, 3}, {4, 4}, {-1, 1}, {-1, 2}, {-1, 3}, {-1, 4}};

MeasChPair currentMeasChPair = {0, 0};

// pin assignment
const int FLOW_STATE_CH[NUM_CHANNELS] = {2, 7, 8, 13};
const int FLOW_SETPOINT_CH[NUM_CHANNELS] = {3, 5, 9, 11};
const int FLOW_MEAS_CH[NUM_CHANNELS] = {A0, A1, A2, A3};

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

void updateMeasureState(char serialBuffer)
{
    int index = getIndexInArray(MEASCHPAIR_COMMANDS, 24, serialBuffer);
    if (index == -1)
        currentMeasChPair = {0, 0};

    currentMeasChPair = measChPairMap[index];
}

void updateMeasureBuffer()
{
    int primaryChIndex = currentMeasChPair.firstCh;
    int secondaryChIndex = currentMeasChPair.secondCh;

    float primaryValue = 0.00;
    float secondaryValue = 0.00;

    if (primaryChIndex > 0)
    {
        primaryValue = analogRead(FLOW_MEAS_CH[primaryChIndex - 1]) * 100.00;
    }
    if (secondaryChIndex > 0)
    {
        secondaryValue = analogRead(FLOW_MEAS_CH[secondaryChIndex - 1]) / 100.00;
    }

    MeasureBuffer = primaryValue + secondaryValue;
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
    currentMeasChPair = {0, 0};
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
        else if (isInArray(MEASCHPAIR_COMMANDS, 24, serialBuffer))
        {
            updateMeasureState(serialBuffer);
        }
    }

    updateMeasureBuffer();
    Serial.println(MeasureBuffer);
    delay(10);
}