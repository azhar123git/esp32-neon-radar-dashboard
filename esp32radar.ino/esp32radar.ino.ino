#include <ESP32Servo.h>

#define SERVO_PIN 13
#define TRIG_PIN  14
#define ECHO_PIN  27

const int MAX_DISTANCE_CM = 200;
const int STEP_ANGLE = 2;
const int SETTLE_TIME_MS = 35;

Servo radarServo;

long readOneDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(3);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 25000);

  if (duration == 0) {
    return -1;
  }

  long cm = duration * 0.0343 / 2.0;

  if (cm < 2 || cm > MAX_DISTANCE_CM) {
    return -1;
  }

  return cm;
}

long getFilteredDistance() {
  long values[3];
  int count = 0;

  for (int i = 0; i < 3; i++) {
    long cm = readOneDistance();

    if (cm >= 0) {
      values[count++] = cm;
    }

    delay(5);
  }

  if (count == 0) {
    return -1;
  }

  // Sort the valid readings
  for (int i = 0; i < count - 1; i++) {
    for (int j = i + 1; j < count; j++) {
      if (values[j] < values[i]) {
        long temp = values[i];
        values[i] = values[j];
        values[j] = temp;
      }
    }
  }

  return values[count / 2];
}

void scanAtAngle(int angle) {
  radarServo.write(angle);
  delay(SETTLE_TIME_MS);

  long distance = getFilteredDistance();

  Serial.print("Angle: ");
  Serial.print(angle);
  Serial.print(" deg | ");

  if (distance < 0) {
    Serial.println("No valid echo");
  } else {
    Serial.print("Distance: ");
    Serial.print(distance);
    Serial.println(" cm");
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  radarServo.setPeriodHertz(50);
  radarServo.attach(SERVO_PIN, 500, 2400);
  radarServo.write(90);

  delay(500);
  Serial.println("FILTERED ESP32 RADAR READY");
}

void loop() {
  for (int angle = 0; angle <= 180; angle += STEP_ANGLE) {
    scanAtAngle(angle);
  }

  for (int angle = 180; angle >= 0; angle -= STEP_ANGLE) {
    scanAtAngle(angle);
  }
}