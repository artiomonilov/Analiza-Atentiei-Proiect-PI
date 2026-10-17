# Detector facial YuNet

`face_detection_yunet_2023mar.onnx` este distribuit nemodificat din [OpenCV Zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet).

SHA-256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`.

Licența MIT originală este inclusă în `YUNET-LICENSE`.
Detectorul fixat este utilizat atât la preprocesarea datasetului, cât și în aplicație.
Intrare de 320×320, redimensionare proporțională și completare cu negru; prag scor 0.8, NMS 0.3.
Nu este un clasificator de angajament și nu necesită descărcări la pornirea aplicației.
