(() => {
  'use strict';
  const dialog = document.getElementById('deficiency-report-dialog');
  if (dialog && typeof dialog.showModal === 'function') {
    document.querySelector('[data-deficiency-report-open]')?.addEventListener('click', event => { event.preventDefault(); dialog.showModal(); });
    dialog.querySelector('[data-deficiency-report-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', event => { if(event.target===dialog) { const r=dialog.getBoundingClientRect(); if(event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) dialog.close(); } });
  }
  const months = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  const latin = value => value.replace(/[۰-۹٠-٩]/g, c => '۰۱۲۳۴۵۶۷۸۹'.includes(c) ? '۰۱۲۳۴۵۶۷۸۹'.indexOf(c) : '٠١٢٣٤٥٦٧٨٩'.indexOf(c));
  const dateString = (year,month,day) => `${year}/${String(month).padStart(2,'0')}/${String(day).padStart(2,'0')}`;
  document.querySelectorAll('.deficiency-report-form').forEach(form => {
    const status = form.querySelector('[data-report-status]');
    form.querySelectorAll('.deficiency-report-date').forEach(field => {
      const input = field.querySelector('input');
      const toggle = field.querySelector('[data-date-picker]');
      const popup = field.querySelector('.deficiency-report-calendar');
      let requestId=0, shown=null;
      const close = () => { popup.hidden=true; toggle.setAttribute('aria-expanded','false'); };
      const button = (label, action, aria) => { const b=document.createElement('button'); b.type='button'; b.textContent=label; if(aria) b.setAttribute('aria-label',aria); b.addEventListener('click',action); return b; };
      async function load(year,month) {
        const id=++requestId;
        try {
          const url=new URL(form.dataset.calendarUrl, location.origin);
          if(year && month) { url.searchParams.set('year',year); url.searchParams.set('month',month); }
          const response=await fetch(url,{headers:{Accept:'application/json'}});
          if(!response.ok) throw Error('calendar');
          const data=await response.json();
          if(id!==requestId) return;
          shown=data; popup.replaceChildren();
          const header=document.createElement('header');
          const step=delta => { let m=shown.month+delta, y=shown.year; if(m<1) {m=12;y--;} if(m>12) {m=1;y++;} load(y,m); };
          const title=document.createElement('strong'); title.textContent=`${months[data.month-1]} ${data.year.toLocaleString('fa-IR',{useGrouping:false})}`; title.setAttribute('aria-live','polite');
          header.append(button('→',()=>step(-1),'ماه قبل'),title,button('←',()=>step(1),'ماه بعد')); popup.append(header);
          const grid=document.createElement('div'); grid.className='deficiency-report-calendar-grid';
          ['ش','ی','د','س','چ','پ','ج'].forEach(day => {const s=document.createElement('span');s.textContent=day;grid.append(s);});
          for(let i=0;i<data.offset;i++) grid.append(document.createElement('span'));
          for(let day=1;day<=data.days;day++) {
            const value=dateString(data.year,data.month,day);
            const b=button(day.toLocaleString('fa-IR'),()=>{input.value=value;input.dispatchEvent(new Event('change',{bubbles:true}));close();toggle.focus();},`${day} ${months[data.month-1]} ${data.year}`);
            b.setAttribute('aria-pressed',String(value===latin(input.value))); b.dataset.today=String(value===data.today); grid.append(b);
          }
          popup.append(grid,button('امروز',()=>{input.value=data.today;close();toggle.focus();}));
        } catch (_) { if(id===requestId) {popup.textContent='تقویم بارگیری نشد؛ تاریخ را دستی وارد کنید.';} }
      }
      toggle.addEventListener('click',()=>{
        if(!popup.hidden) {close();return;}
        popup.hidden=false; toggle.setAttribute('aria-expanded','true');
        const parts=latin(input.value).trim().split(/[/-]/).map(Number);
        load(parts[0]>=1200 && parts[0]<=1600 ? parts[0] : null,parts[1]);
      });
      document.addEventListener('click',event=>{if(!field.contains(event.target)) close();});
      field.addEventListener('keydown',event=>{if(event.key==='Escape' && !popup.hidden) {event.preventDefault();event.stopPropagation();close();toggle.focus();}});
    });
    form.addEventListener('submit',async event=>{
      if(!window.fetch || !window.URL.createObjectURL) return;
      event.preventDefault();
      const submit=form.querySelector('button[type=submit]');
      if(submit.disabled) return;
      submit.disabled=true;status.dataset.success='false';status.textContent='در حال آماده‌سازی فایل اکسل…';
      try {
        const url=new URL(form.action,location.origin);url.search=new URLSearchParams(new FormData(form)).toString();
        const response=await fetch(url,{headers:{Accept:'application/json'}});
        if(response.status===400 && response.headers.get('Content-Type')?.includes('application/json')) {
          const result=await response.json();status.textContent=Object.values(result.errors).flat().map(error=>error.message).join(' ');return;
        }
        if(!response.ok || !response.headers.get('Content-Type')?.includes('spreadsheetml.sheet')) throw Error('download');
        const blob=await response.blob();const objectUrl=URL.createObjectURL(blob);const link=document.createElement('a');
        link.href=objectUrl;link.download=/filename="([^"]+)"/.exec(response.headers.get('Content-Disposition')||'')?.[1]||'homework-deficiencies.xlsx';
        document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(objectUrl),60000);
        status.dataset.success='true';status.textContent='فایل اکسل آماده شد؛ دانلود آغاز شد.';
      } catch (_) {status.textContent='دریافت گزارش انجام نشد. اتصال و ورود به حساب را بررسی و دوباره تلاش کنید.';}
      finally {submit.disabled=false;}
    });
  });
})();
