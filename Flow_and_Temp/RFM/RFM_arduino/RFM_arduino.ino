int serialBuffer;       // serialBuffer는 시리얼 통신으로 processing에서 받는 문자열이다.
int FlowRateBuffer = 0; // FlowRateBuffer는 flowrate 설정에서 processing에서 받는 정수열을 저장하는 변수이다.
int value;              // value는 flowrate 설정에서 processing에서 받는 정수열(0-200)을 아두이노에서 사용하는(0-4095)로 바꾼 변수이다.
int MeasureState = 0;
float MeasureBuffer = 0.000;

const int FLOW_STATE_CH1 = 2;
const int FLOW_STATE_CH2 = 7;
const int FLOW_STATE_CH3 = 8;
const int FLOW_STATE_CH4 = 13;

const int FLOW_SETPOINT_CH1 = 3;
const int FLOW_SETPOINT_CH2 = 5;
const int FLOW_SETPOINT_CH3 = 9;
const int FLOW_SETPOINT_CH4 = 11;

const int FLOW_MEASUREMENT_CH1 = A0;
const int FLOW_MEASUREMENT_CH2 = A1;
const int FLOW_MEASUREMENT_CH3 = A2;
const int FLOW_MEASUREMENT_CH4 = A3;

void setup()
{
    // put your setup code here, to run once:
    Serial.begin(9600); // 시리얼 통신(9600)을 개시한다.
    // FLOW STATE, DIGITAL OUTPUT
    pinMode(FLOW_STATE_CH1, OUTPUT); // CH1 FLOW STATE
    pinMode(FLOW_STATE_CH2, OUTPUT); // CH2 FLOW STATE
    pinMode(FLOW_STATE_CH3, OUTPUT); // CH3 FLOW STATE
    pinMode(FLOW_STATE_CH4, OUTPUT); // CH4 FLOW STATE
    // FLOW SETPOINT, ANALOG OUTPUT
    pinMode(FLOW_SETPOINT_CH1, OUTPUT); // CH1 FLOW SETPOINT
    pinMode(FLOW_SETPOINT_CH2, OUTPUT); // CH2 FLOW SETPOINT
    pinMode(FLOW_SETPOINT_CH3, OUTPUT); // CH3 FLOW SETPOINT
    pinMode(FLOW_SETPOINT_CH4, OUTPUT); // CH4 FLOW SETPOINT
    // FLOW MEASUREMENT, ANALOG INPUT
    pinMode(FLOW_MEASUREMENT_CH1, INPUT); // CH1 FLOW MEASUREMENT
    pinMode(FLOW_MEASUREMENT_CH2, INPUT); // CH2 FLOW MEASUREMENT
    pinMode(FLOW_MEASUREMENT_CH3, INPUT); // CH3 FLOW MEASUREMENT
    pinMode(FLOW_MEASUREMENT_CH4, INPUT); // CH4 FLOW MEASUREMENT
    // INITIAL FLOW STATE : OFF
    digitalWrite(FLOW_STATE_CH1, HIGH);
    digitalWrite(FLOW_STATE_CH2, HIGH);
    digitalWrite(FLOW_STATE_CH3, HIGH);
    digitalWrite(FLOW_STATE_CH4, HIGH);
    // INNITIAL FLOW SETPOINT : 0.55V
    analogWrite(FLOW_SETPOINT_CH1, 0);
    analogWrite(FLOW_SETPOINT_CH2, 0);
    analogWrite(FLOW_SETPOINT_CH3, 0);
    analogWrite(FLOW_SETPOINT_CH4, 0);
}

void loop()
{
    while (Serial.available()) // 시리얼 통신이 가능한 동안
    {
        serialBuffer = Serial.read(); // serialBuffer는 시리얼에서 받은 값이다.

        // ON-OFF PART (HIGH : 3.3 V (close), LOW : 0 V (open))
        // 2, 7, 8, 13 : Ch1, Ch2, Ch3, Ch4 FLOW STATE
        if (serialBuffer == 'a')
            digitalWrite(2, HIGH);
        if (serialBuffer == 'z')
            analogWrite(2, LOW);
        if (serialBuffer == 's')
            digitalWrite(7, HIGH);
        if (serialBuffer == 'x')
            analogWrite(7, LOW);
        if (serialBuffer == 'd')
            digitalWrite(8, HIGH);
        if (serialBuffer == 'c')
            analogWrite(8, LOW);
        if (serialBuffer == 'f')
            digitalWrite(13, HIGH);
        if (serialBuffer == 'v')
            analogWrite(13, LOW);

        // FLOW RATE BUFFER PART
        if ((serialBuffer >= '0') && (serialBuffer <= '9'))
        {
            FlowRateBuffer = 10 * FlowRateBuffer + serialBuffer - '0';
        }

        // FLOW RATE SETTING PART
        else if (serialBuffer == 'q')
        {
            value = map(FlowRateBuffer, 0, 200, 0, 255);
            analogWrite(3, value);
            FlowRateBuffer = 0;
        }
        else if (serialBuffer == 'w')
        {
            value = map(FlowRateBuffer, 0, 200, 0, 255);
            analogWrite(5, value);
            FlowRateBuffer = 0;
        }
        else if (serialBuffer == 'e')
        {
            value = map(FlowRateBuffer, 0, 200, 0, 255);
            analogWrite(9, value);
            FlowRateBuffer = 0;
        }
        else if (serialBuffer == 'r')
        {
            value = map(FlowRateBuffer, 0, 200, 0, 255);
            analogWrite(11, value);
            FlowRateBuffer = 0;
        }

        // RESET PART
        if (serialBuffer == 'B')
        {
            digitalWrite(2, HIGH);
            digitalWrite(7, HIGH);
            digitalWrite(8, HIGH);
            digitalWrite(13, HIGH);
            analogWrite(3, 0);
            analogWrite(5, 0);
            analogWrite(9, 0);
            analogWrite(11, 0);
            MeasureState = 0;
        }

        // FLOW RATE MEASUREMENT PART
        // analogRead의 범위는 0-4095이다. TODO: 믿을만한 정보는 아닌 것 같다.

        if (serialBuffer == 't')
        {
            MeasureState = 10;
        }
        if (serialBuffer == 'y')
        {
            MeasureState = 11;
        }
        if (serialBuffer == 'u')
        {
            MeasureState = 12;
        }
        if (serialBuffer == 'i')
        {
            MeasureState = 13;
        }
        if (serialBuffer == 'o')
        {
            MeasureState = 14;
        }
        if (serialBuffer == 'p')
        {
            MeasureState = 20;
        }
        if (serialBuffer == 'g')
        {
            MeasureState = 21;
        }
        if (serialBuffer == 'h')
        {
            MeasureState = 22;
        }
        if (serialBuffer == 'j')
        {
            MeasureState = 23;
        }
        if (serialBuffer == 'k')
        {
            MeasureState = 24;
        }
        if (serialBuffer == 'l')
        {
            MeasureState = 30;
        }
        if (serialBuffer == 'b')
        {
            MeasureState = 31;
        }
        if (serialBuffer == 'n')
        {
            MeasureState = 32;
        }
        if (serialBuffer == 'm')
        {
            MeasureState = 33;
        }
        if (serialBuffer == 'Q')
        {
            MeasureState = 34;
        }
        if (serialBuffer == 'W')
        {
            MeasureState = 40;
        }
        if (serialBuffer == 'E')
        {
            MeasureState = 41;
        }
        if (serialBuffer == 'R')
        {
            MeasureState = 42;
        }
        if (serialBuffer == 'T')
        {
            MeasureState = 43;
        }
        if (serialBuffer == 'Y')
        {
            MeasureState = 44;
        }
        if (serialBuffer == 'U')
        {
            MeasureState = 1;
        }
        if (serialBuffer == 'I')
        {
            MeasureState = 2;
        }
        if (serialBuffer == 'O')
        {
            MeasureState = 3;
        }
        if (serialBuffer == 'P')
        {
            MeasureState = 4;
        }
    }

    if (MeasureState == 10)
    {
        MeasureBuffer = (analogRead(A0) * 100.00);
    }
    if (MeasureState == 11)
    {
        MeasureBuffer = (analogRead(A0) * 100.00 + analogRead(A0) / 100.00);
    }
    if (MeasureState == 12)
    {
        MeasureBuffer = (analogRead(A0) * 100.00 + analogRead(A1) / 100.00);
    }
    if (MeasureState == 13)
    {
        MeasureBuffer = (analogRead(A0) * 100.00 + analogRead(A2) / 100.00);
    }
    if (MeasureState == 14)
    {
        MeasureBuffer = (analogRead(A0) * 100.00 + analogRead(A3) / 100.00);
    }
    if (MeasureState == 20)
    {
        MeasureBuffer = (analogRead(A1) * 100.00);
    }
    if (MeasureState == 21)
    {
        MeasureBuffer = (analogRead(A1) * 100.00 + analogRead(A0) / 100.00);
    }
    if (MeasureState == 22)
    {
        MeasureBuffer = (analogRead(A1) * 100.00 + analogRead(A1) / 100.00);
    }
    if (MeasureState == 23)
    {
        MeasureBuffer = (analogRead(A1) * 100.00 + analogRead(A2) / 100.00);
    }
    if (MeasureState == 24)
    {
        MeasureBuffer = (analogRead(A1) * 100.00 + analogRead(A3) / 100.00);
    }
    if (MeasureState == 30)
    {
        MeasureBuffer = (analogRead(A2) * 100.00);
    }
    if (MeasureState == 31)
    {
        MeasureBuffer = (analogRead(A2) * 100.00 + analogRead(A0) / 100.00);
    }
    if (MeasureState == 32)
    {
        MeasureBuffer = (analogRead(A2) * 100.00 + analogRead(A1) / 100.00);
    }
    if (MeasureState == 33)
    {
        MeasureBuffer = (analogRead(A2) * 100.00 + analogRead(A2) / 100.00);
    }
    if (MeasureState == 34)
    {
        MeasureBuffer = (analogRead(A2) * 100.00 + analogRead(A3) / 100.00);
    }
    if (MeasureState == 40)
    {
        MeasureBuffer = (analogRead(A3) * 100.00);
    }
    if (MeasureState == 41)
    {
        MeasureBuffer = (analogRead(A3) * 100.00 + analogRead(A0) / 100.00);
    }
    if (MeasureState == 42)
    {
        MeasureBuffer = (analogRead(A3) * 100.00 + analogRead(A1) / 100.00);
    }
    if (MeasureState == 43)
    {
        MeasureBuffer = (analogRead(A3) * 100.00 + analogRead(A2) / 100.00);
    }
    if (MeasureState == 44)
    {
        MeasureBuffer = (analogRead(A3) * 100.00 + analogRead(A3) / 100.00);
    }
    if (MeasureState == 1)
    {
        MeasureBuffer = (analogRead(A0) / 100.00);
    }
    if (MeasureState == 2)
    {
        MeasureBuffer = (analogRead(A1) / 100.00);
    }
    if (MeasureState == 3)
    {
        MeasureBuffer = (analogRead(A2) / 100.00);
    }
    if (MeasureState == 4)
    {
        MeasureBuffer = (analogRead(A3) / 100.00);
    }
    if (MeasureState == 0)
    {
        MeasureBuffer = 0.00;
    }
    Serial.println(MeasureBuffer);
    delay(10);
}