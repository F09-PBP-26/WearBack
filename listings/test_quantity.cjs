const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../static/js/listings.js'), 'utf8');

class Input extends EventTarget {
  constructor(value) {
    super();
    this.value = value;
  }

  get value() { return this.currentValue; }
  set value(value) { this.currentValue = String(value); }
  get valueAsNumber() { return this.value === '' ? NaN : Number(this.value); }
}

function quantityPage({ stock = 3, initial = '1', authenticated = true } = {}) {
  const input = new Input(initial);
  input.max = String(stock);
  const decrease = new EventTarget();
  const increase = new EventTarget();
  const submittedQuantity = new Input('1');
  const status = { textContent: '' };
  const control = {
    querySelector(selector) {
      return {
        '[data-quantity-input]': input,
        '[data-quantity-decrease]': decrease,
        '[data-quantity-increase]': increase,
      }[selector] || null;
    },
  };
  const form = { querySelector: () => submittedQuantity };
  const document = {
    querySelectorAll: (selector) => selector === '[data-quantity-control]' ? [control] : [],
    querySelector(selector) {
      return {
        '[data-quantity-status]': status,
        '[data-add-to-cart-form]': authenticated ? form : null,
      }[selector] || null;
    },
  };
  vm.runInNewContext(script, { document });
  return {
    input, decrease, increase, submittedQuantity, status,
    click(button) { if (!button.disabled) button.dispatchEvent(new Event('click')); },
    enter(value, event) {
      input.value = value;
      input.dispatchEvent(new Event(event));
    },
  };
}

test('quantity buttons submit the displayed quantity and respect stock bounds', () => {
  const page = quantityPage();
  assert.equal(page.submittedQuantity.value, '1');
  assert.equal(page.decrease.disabled, true);

  page.click(page.increase);
  page.click(page.increase);
  assert.equal(page.input.value, '3');
  assert.equal(page.submittedQuantity.value, '3');
  assert.equal(page.status.textContent, 'Quantity: 3');
  assert.equal(page.increase.disabled, true);

  page.click(page.decrease);
  assert.equal(page.input.value, '2');
  assert.equal(page.submittedQuantity.value, '2');
  page.click(page.decrease);
  assert.equal(page.submittedQuantity.value, '1');
  assert.equal(page.decrease.disabled, true);
});

test('typed, changed, and cleared quantities submit their normalized value', () => {
  const page = quantityPage();
  for (const [value, event, expected] of [
    ['2', 'input', '2'],
    ['99', 'change', '3'],
    ['0', 'input', '1'],
    ['2.7', 'change', '2'],
    ['', 'blur', '1'],
  ]) {
    page.enter(value, event);
    assert.equal(page.input.value, expected);
    assert.equal(page.submittedQuantity.value, expected);
  }
});

test('initial quantities are normalized before submission', () => {
  const page = quantityPage({ stock: 1, initial: '5' });
  assert.equal(page.input.value, '1');
  assert.equal(page.submittedQuantity.value, '1');
  assert.equal(page.decrease.disabled, true);
  assert.equal(page.increase.disabled, true);
});

test('guest quantity controls work without an add-to-cart form', () => {
  const page = quantityPage({ authenticated: false });
  page.click(page.increase);
  assert.equal(page.input.value, '2');
  assert.equal(page.status.textContent, 'Quantity: 2');
});
