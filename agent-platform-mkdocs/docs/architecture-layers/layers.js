const choices = Array.from(document.querySelectorAll('input[name="layer"]'));
const layers = document.querySelectorAll('.layer');
const previous = document.querySelector('#back');
const next = document.querySelector('#forward');
const status = document.querySelector('#stage');

function showThrough(index) {
  const choice = choices[index];
  choice.checked = true;
  layers.forEach((layer, position) => {
    layer.hidden = position > index;
  });
  previous.disabled = index === 0;
  next.disabled = index === choices.length - 1;
  status.textContent = `Layer ${index + 1} of ${choices.length} · ${choice.parentElement.textContent.trim()}`;
}

function selectedIndex() {
  return choices.findIndex(choice => choice.checked);
}

document.querySelector('#layer-picker').addEventListener('change', () => showThrough(selectedIndex()));
previous.addEventListener('click', () => showThrough(selectedIndex() - 1));
next.addEventListener('click', () => showThrough(selectedIndex() + 1));
showThrough(selectedIndex());
