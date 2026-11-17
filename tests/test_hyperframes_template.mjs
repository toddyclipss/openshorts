import { spawn } from 'node:child_process';
import path from 'node:path';

const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function run() {
  const p = spawn(chromePath, [
    '--headless',
    '--remote-debugging-port=9666',
    '--disable-gpu',
    '--allow-file-access-from-files'
  ]);

  await new Promise((r) => setTimeout(r, 1200));

  const indexPath = 'file:///' + path.resolve('templates/short-video/index.html').replace(/\\/g, '/');
  const newTabRes = await fetch('http://127.0.0.1:9666/json/new?' + encodeURIComponent(indexPath), {
    method: 'PUT'
  });
  const tab = await newTabRes.json();

  const ws = new WebSocket(tab.webSocketDebuggerUrl);
  await new Promise((resolve) => {
    ws.onopen = resolve;
  });

  let msgId = 1;
  function send(method, params = {}) {
    return new Promise((resolve) => {
      const id = msgId++;
      const handler = (evt) => {
        const data = JSON.parse(evt.data);
        if (data.id === id) {
          ws.removeEventListener('message', handler);
          resolve(data.result);
        }
      };
      ws.addEventListener('message', handler);
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  // Wait for fonts & DOM load
  await new Promise((r) => setTimeout(r, 1000));

  // Evaluate initial DOM & GSAP state
  const eval1 = await send('Runtime.evaluate', {
    expression: `({
      hasGsap: typeof window.gsap === 'object',
      hasTimeline: !!(window.__timelines && window.__timelines['root']),
      hookText: document.getElementById('hook-text')?.textContent,
      wordsCount: document.querySelectorAll('.word-span').length,
      stickersCount: document.querySelectorAll('.viral-sticker').length,
      hasRetentionBar: !!document.getElementById('retention-bar'),
      duration: window.__timelines?.root?.duration()
    })`,
    returnByValue: true
  });

  console.log('--- Initial State Check ---');
  console.log(eval1.result.value);

  // Seek to 2.0s
  const eval2 = await send('Runtime.evaluate', {
    expression: `(() => {
      window.seek(2.0);
      return {
        time: window.__timelines.root.time(),
        hookOpacity: window.getComputedStyle(document.getElementById('hook-box')).opacity,
        videoZoom: window.getComputedStyle(document.getElementById('video-wrapper')).transform
      };
    })()`,
    returnByValue: true
  });

  console.log('--- Seek 2.0s Check ---');
  console.log(eval2.result.value);

  // Seek to 4.5s
  const eval3 = await send('Runtime.evaluate', {
    expression: `(() => {
      window.seek(4.5);
      return {
        time: window.__timelines.root.time(),
        hookDisplay: window.getComputedStyle(document.getElementById('hook-wrapper')).display
      };
    })()`,
    returnByValue: true
  });

  console.log('--- Seek 4.5s Check ---');
  console.log(eval3.result.value);

  ws.close();
  await fetch('http://127.0.0.1:9666/json/close/' + tab.id);
  p.kill();

  if (
    eval1.result.value.hasGsap &&
    eval1.result.value.hasTimeline &&
    eval1.result.value.wordsCount > 0 &&
    eval1.result.value.stickersCount > 0 &&
    eval1.result.value.hasRetentionBar &&
    eval2.result.value.time === 2
  ) {
    console.log('\n[PASS] HyperFrames short-video template is completely valid and functional!');
    process.exit(0);
  } else {
    console.error('\n[FAIL] Validation assertions failed');
    process.exit(1);
  }
}

run().catch((err) => {
  console.error('Fatal test error:', err);
  process.exit(1);
});
