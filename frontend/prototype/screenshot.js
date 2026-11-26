const path = require("path");
const { chromium } = require("playwright");

const screens = ["start", "uploaded", "result", "error"];

(async () => {
  const browser = await chromium.launch({
    executablePath: "/opt/pw-browsers/chromium",
  });
  const page = await browser.newPage({ viewport: { width: 460, height: 700 } });
  const filePath = "file://" + path.resolve(__dirname, "index.html");
  await page.goto(filePath);

  for (const screen of screens) {
    await page.click(`.tab[data-screen="${screen}"]`);
    await page.waitForTimeout(150);
    await page.screenshot({
      path: path.resolve(__dirname, `screenshots/${screen}.png`),
      clip: { x: 0, y: 0, width: 460, height: 700 },
    });
  }

  await browser.close();
  console.log("done");
})();
