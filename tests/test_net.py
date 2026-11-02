from transformers import pipeline

pipe = pipeline("image-classification", model="trpakov/vit-face-expression")


# 2. Imaginea analizată
image_url = "https://previews.123rf.com/images/samwordley/samwordley1907/samwordley190701636/127609842-young-man-feeling-scared-and-shocked-making-fear-anxiety-gestures-looking-terrified-and-desperate.jpg"
# 3. Rulăm clasificarea
result = pipe(image_url)

# 4. Afișăm rezultatul
print("Rezultatul clasificării:")
for item in result:
    print(f"Emoție: {item['label']}, Scor: {item['score']:.4f}")

# 5. Afișăm predicția principală
best_result = result[0]
print("\nPredicția principală:")
print(f"Etichetă: {best_result['label']}")
print(f"Scor: {best_result['score']:.2%}")
