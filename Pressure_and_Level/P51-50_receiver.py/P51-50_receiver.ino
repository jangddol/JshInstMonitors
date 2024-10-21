float filtered_value = NAN;
float beta = 0.9391; // np.exp(-2*np.pi*1ms/100ms)
int time_index = 0;

void setup()
{
  // Initialize serial communication
  Serial.begin(9600);

  // Pin Setting
  pinMode(A0, INPUT);
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
  int value = analogRead(A0);
  float value_float = static_cast<float>(value);
  filtered_value = low_pass_filter(value_float, filtered_value, beta);

  if (time_index == 99)
  {
    time_index = 0;
    Serial.println(filtered_value);
  }
  delay(1);
  time_index++;
}
