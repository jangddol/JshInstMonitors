float beta = 0.5335; // np.exp(-2*np.pi*1ms/10ms)
int time_index = 0;
const int period = 500;

const int PIN_NUM = 1;
const int assigned_pins[PIN_NUM] = {A0};
float filtered_values[PIN_NUM] = {NAN};

void setup()
{
  const int baud_rate = 9600;
  Serial.begin(baud_rate);

  for (int i = 0; i < PIN_NUM; i++)
  {
    pinMode(assigned_pins[i], INPUT);
  }
}

float low_pass_filter(float value, float last_filtered_value, float beta)
{
  float answer;
  if (isnan(last_filtered_value))
  {
    answer = value;
  }
  else
  {
    answer = beta * last_filtered_value + (1 - beta) * value;
  }
  return answer;
}

void loop()
{
  int values_bit[PIN_NUM];
  float values_float[PIN_NUM];
  for (int i = 0; i < PIN_NUM; i++)
  {
    values_bit[i] = analogRead(assigned_pins[i]);
    values_float[i] = static_cast<float>(values_bit[i]);
    filtered_values[i] = low_pass_filter(values_float[i], filtered_values[i], beta);
  }

  if (time_index == period - 1)
  {
    time_index = 0;
    for (int i = 0; i < PIN_NUM; i++)
    {
      Serial.print(filtered_values[i]);
      if (i < PIN_NUM - 1)
      {
        Serial.print(",");
      }
    }
    Serial.println();
  }
  delay(1);
  time_index++;
}
