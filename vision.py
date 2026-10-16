import cv2, requests, time
from ultralytics import YOLO

VIDEO = 0      # "busy.mp4" to test people, or 0 for webcam
ROOM_ID = "block-b"      # must match a backend room id (CD Simer)
API = "http://127.0.0.1:8000"
EMPTY_SECONDS = 5        # how long empty before the alert

model = YOLO("yolov8n.pt")
cap = cv2.VideoCapture(VIDEO)
if not cap.isOpened():
    raise SystemExit("Cannot open video. Check the file name and folder.")

empty_since = None
alerted = False

while True:
    ok, frame = cap.read()
    if not ok:                                  # video ended, loop it
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        continue

    result = model(frame, classes=[0],conf=0.45, verbose=False)[0]   # class 0 = person
    persons = len(result.boxes)
    shown = result.plot()

    if persons == 0:
        if empty_since is None:
            empty_since = time.time()
        waited = time.time() - empty_since
        if waited >= EMPTY_SECONDS and not alerted:
            try:
                requests.post(f"{API}/simulate/empty-room/{ROOM_ID}", timeout=3)
                print("ALERT sent: room empty, lights ON")
            except Exception as e:
                print("API error:", e)
            alerted = True
        label, color = f"Persons: 0 (empty {int(waited)}s)", (0, 0, 255)
    else:
        empty_since, alerted = None, False
        label, color = f"Persons: {persons}", (0, 200, 0)

    cv2.putText(shown, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 3)
    cv2.imshow("CampusMind CCTV (press q to quit)", shown)
    if cv2.waitKey(30) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()