(function () {
  const btn = document.getElementById('run-digest-btn');
  const banner = document.getElementById('digest-job-banner');
  const messageEl = document.getElementById('digest-job-message');
  const actionsEl = document.getElementById('digest-job-actions');
  if (!btn || !banner) {
    return;
  }

  const postEl = document.getElementById('digest-job-post');

  let pollTimer = null;

  function renderActions(job) {
    actionsEl.replaceChildren();
    if (job.state !== 'completed' && job.state !== 'failed') {
      return;
    }

    const dismissBtn = document.createElement('button');
    dismissBtn.type = 'button';
    dismissBtn.id = 'digest-job-dismiss';
    dismissBtn.className = 'btn btn-ghost btn-sm';
    dismissBtn.textContent = 'Dismiss';
    dismissBtn.addEventListener('click', dismissJob);
    actionsEl.appendChild(dismissBtn);

    if (job.state === 'completed' && job.digest_id) {
      const link = document.createElement('a');
      link.href = '/?id=' + String(job.digest_id);
      link.className = 'btn btn-sm';
      link.textContent = 'View digest';
      actionsEl.appendChild(link);
    }
  }

  function setBanner(job) {
    banner.dataset.state = job.state;
    messageEl.textContent = job.message || '';
    if (postEl) {
      const lines = job.state === 'failed' ? job.post_display || '' : '';
      postEl.textContent = lines;
      postEl.classList.toggle('is-hidden', !lines);
    }
    banner.classList.toggle(
      'is-hidden',
      !['running', 'completed', 'failed'].includes(job.state),
    );
    banner.classList.toggle('job-banner--running', job.state === 'running');
    banner.classList.toggle('job-banner--failed', job.state === 'failed');
    banner.classList.toggle('job-banner--done', job.state === 'completed');

    btn.disabled = job.state === 'running';
    btn.textContent = job.state === 'running' ? 'Running…' : 'Run digest';

    if (job.state === 'completed' || job.state === 'failed') {
      renderActions(job);
    } else {
      actionsEl.replaceChildren();
    }
  }

  async function fetchStatus() {
    const res = await fetch('/api/digest/status');
    return res.json();
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function startPolling() {
    stopPolling();
    pollTimer = setInterval(async () => {
      try {
        const job = await fetchStatus();
        setBanner(job);
        if (job.state !== 'running') {
          stopPolling();
        }
      } catch (_err) {
        stopPolling();
        messageEl.textContent = 'Lost connection while checking status.';
        banner.classList.remove('is-hidden');
        banner.classList.add('job-banner--failed');
      }
    }, 2000);
  }

  async function startRun() {
    btn.disabled = true;
    btn.textContent = 'Starting…';
    try {
      const res = await fetch('/api/digest/run', { method: 'POST' });
      const data = await res.json();
      if (!data.ok) {
        setBanner(data.job || { state: 'failed', message: data.message });
        btn.disabled = false;
        btn.textContent = 'Run digest';
        return;
      }
      setBanner(data.job);
      startPolling();
    } catch (_err) {
      setBanner({ state: 'failed', message: 'Could not start digest run.' });
      btn.disabled = false;
      btn.textContent = 'Run digest';
    }
  }

  async function dismissJob() {
    try {
      const res = await fetch('/api/digest/dismiss', { method: 'POST' });
      const job = await res.json();
      setBanner(job);
    } catch (_err) {
      banner.classList.add('is-hidden');
    }
  }

  btn.addEventListener('click', startRun);

  const dismissOnLoad = document.getElementById('digest-job-dismiss');
  if (dismissOnLoad) {
    dismissOnLoad.addEventListener('click', dismissJob);
  }

  if (banner.dataset.state === 'running') {
    startPolling();
  }
})();
