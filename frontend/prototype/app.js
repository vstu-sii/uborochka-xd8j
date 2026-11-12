// Прототип ключевых экранов чата с ботом «Уборочка».
// Переключение между четырьмя состояниями диалога: старт, фото отправлено,
// готовая оценка, ошибка анализа. Никакой сборки — чистый DOM + классы.

const tabs = document.querySelectorAll(".tab");
const screens = document.querySelectorAll(".screen");
const form = document.querySelector("#inspection-form");
const submitButton = document.querySelector("#submit-inspection");
const uploadedImage = document.querySelector("#uploaded-image");
const resultImage = document.querySelector(".result-image");
const errorImage = document.querySelector(".error-image");
let imageObjectUrl;

function showScreen(target) {
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.screen === target));
  screens.forEach((screen) =>
    screen.classList.toggle("active", screen.id === `screen-${target}`)
  );
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    showScreen(tab.dataset.screen);
  });
});

document.querySelector("#retry-upload").addEventListener("click", () => {
  showScreen("start");
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitButton.disabled = true;

  const image = form.elements.photo.files[0];
  if (image) {
    if (imageObjectUrl) {
      URL.revokeObjectURL(imageObjectUrl);
    }
    imageObjectUrl = URL.createObjectURL(image);
    [uploadedImage, resultImage, errorImage].forEach((element) => {
      element.src = imageObjectUrl;
    });
  }

  showScreen("uploaded");

  try {
    const response = await fetch("/inspection", {
      method: "POST",
      body: new FormData(form),
    });
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.detail || "Не удалось выполнить проверку.");
    }

    document.querySelector("#score").textContent = `${payload.result.score} / 10`;
    document.querySelector("#request-id").textContent =
      `Проверка №${payload.request_id}`;
    document.querySelector("#demo-notice").hidden = !payload.result.is_demo;
    const recommendations = document.querySelector("#recommendations");
    recommendations.replaceChildren(
      ...payload.result.recommendations.map((text) => {
        const item = document.createElement("li");
        item.textContent = text;
        return item;
      })
    );
    showScreen("result");
  } catch (error) {
    document.querySelector("#error-message").textContent =
      error instanceof Error ? error.message : "Не удалось выполнить проверку.";
    showScreen("error");
  } finally {
    submitButton.disabled = false;
  }
});
