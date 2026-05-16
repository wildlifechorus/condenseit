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

  function setBanner(job) {
    banner.dataset.state = job.state;
    messageEl.textContent = job.message || '';
    if (postEl) {
      const lines = job.post_display || '';
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
      let html = '';
      if (job.state === 'completed' || job.state === 'failed') {
        html +=
          '<button type="button" id="digest-job-dismiss" class="btn btn-ghost btn-sm">Dismiss</button>';
      }
      if (job.state === 'completed' && job.digest_id) {
        html +=
          '<a href="/?id=' +
          job.digest_id +
          '" class="btn btn-sm">View digest</a>';
      }
      actionsEl.innerHTML = html;
      const dismiss = document.getElementById('digest-job-dismiss');
      if (dismiss) {
        dismiss.addEventListener('click', dismissJob);
      }
    } else {
      actionsEl.innerHTML = '';
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
