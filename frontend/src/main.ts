import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'
import { UI_EN, translateDynamic } from './lib/ui_text'

const app = mount(App, {
  target: document.getElementById('app')!,
})

export default app

let language = 'zh';
let translations: Record<string, string> = {};
const originalText = new WeakMap<Text, {source: string; rendered: string}>();
function translateLabels(root: Node) {
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node: Node | null;
  while ((node = walk.nextNode())) {
    const text = node as Text;
    if (text.parentElement?.closest('script,style,input,textarea,.font-mono,.mono')) continue;
    let previous = originalText.get(text);
    if (!previous || text.data !== previous.rendered) previous = {source: text.data, rendered: text.data};
    const source = previous.source;
    const key = source.trim();
    const translated = language === 'en' ? (UI_EN[key] || translations[key] || translateDynamic(key)) : key;
    const rendered = translated ? source.replace(key, translated) : source;
    originalText.set(text, {source, rendered});
    if (text.data !== rendered) text.data = rendered;
  }
}
const labelObserver = new MutationObserver(records => {
  for (const record of records) {
    if (record.type === 'characterData') translateLabels(record.target.parentNode || document.body);
    else for (const node of record.addedNodes) translateLabels(node.nodeType === Node.TEXT_NODE ? node.parentNode! : node);
  }
});
labelObserver.observe(document.body, {childList:true, characterData:true, subtree:true});
window.addEventListener('war3-language', ((event: CustomEvent) => {
  language = event.detail.language;
  translations = event.detail.translations || {};
  document.documentElement.lang = language === 'en' ? 'en' : 'zh-CN';
  translateLabels(document.body);
}) as EventListener);

window.addEventListener('pagehide', () => labelObserver.disconnect());
