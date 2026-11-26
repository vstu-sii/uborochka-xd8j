// Прототип ключевых экранов чата с ботом «Уборочка».
// Переключение между четырьмя состояниями диалога: старт, фото отправлено,
// готовая оценка, ошибка анализа. Никакой сборки — чистый DOM + классы.

const tabs = document.querySelectorAll(".tab");
const screens = document.querySelectorAll(".screen");

tabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    const target = tab.dataset.screen;

    tabs.forEach((t) => t.classList.toggle("active", t === tab));
    screens.forEach((s) =>
      s.classList.toggle("active", s.id === `screen-${target}`)
    );
  });
});
