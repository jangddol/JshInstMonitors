float P_st_filtered = NAN;
float V_pl_filtered = NAN;
float P_pl_filtered = NAN;
float beta = 0.9391; // np.exp(-2*np.pi*1ms/100ms)
int time_index = 0;

void setup()
{
  // Initialize serial communication
  Serial.begin(9600);

  // Pin Setting
  pinMode(A0, INPUT);
  pinMode(A8, INPUT);
  pinMode(A15, INPUT);
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
  int P_st_bit = analogRead(A0);
  int P_pl_bit = analogRead(A8);
  int V_pl_bit = analogRead(A15);
  float P_st_float = static_cast<float>(P_st_bit);
  float P_pl_float = static_cast<float>(P_pl_bit);
  float V_pl_float = static_cast<float>(V_pl_bit);
  P_st_filtered = low_pass_filter(P_st_float, P_st_filtered, beta);
  P_pl_filtered = low_pass_filter(P_pl_float, P_pl_filtered, beta);
  V_pl_filtered = low_pass_filter(V_pl_float, V_pl_filtered, beta);

  if (time_index == 99)
  {
    time_index = 0;
    Serial.print(P_st_filtered);
    Serial.print(",");
    Serial.print(P_pl_filtered);
    Serial.print(",");
    Serial.println(V_pl_filtered);
  }
  delay(1);
  time_index++;
}
