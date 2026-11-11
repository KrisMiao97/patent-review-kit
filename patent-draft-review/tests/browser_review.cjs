/* Run: node tests/browser_review.cjs report.html evidence-directory
   Optional environment: PLAYWRIGHT_MODULE, CHROME_PATH. No network required. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const input = path.resolve(process.argv[2]);
const destination = path.resolve(process.argv[3]);
fs.mkdirSync(destination, {recursive:true});
const url = pathToFileURL(input).href;

(async()=>{
  // Software rendering avoids GPU texture wrapping in very tall report screenshots.
  const browser = await chromium.launch({headless:true, args:['--disable-gpu'], ...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {})});
  const result = {file:input, widths:[], screenshots:[], errors:[]};
  const shot = async (page, name, extra={}) => {
    const file=path.join(destination,name+'.png');
    await page.screenshot({path:file,...extra}); result.screenshots.push(file);
  };
  try {
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    page.on('pageerror', error=>result.errors.push(error.message));
    await page.goto(url);
    const ids=await page.locator('[id]').evaluateAll(nodes=>nodes.map(n=>n.id));
    assert.equal(ids.length,new Set(ids).size,'duplicate IDs');
    const broken=await page.locator('a[href^="#"]').evaluateAll(nodes=>nodes.map(n=>n.hash.slice(1)).filter(id=>!document.getElementById(id)));
    assert.deepEqual(broken,[],'broken internal links');
    result.issues=await page.locator('article.issue').count();
    result.evidence=await page.locator('#evidence tr[data-claim]').count();
    result.figures=await page.locator('#figures tr[data-related]').count();
    result.images=await page.locator('#drawing-pages img').count();
    for (const img of await page.locator('#drawing-pages img').all()) {
      assert.ok(await img.evaluate(n=>n.complete && n.naturalWidth>0),'embedded image did not load');
    }
    await shot(page,'overview-1440');
    await shot(page,'full-1440',{fullPage:true});
    const filters=[['section-filter','article.issue','section'],['issue-filter','article.issue','status'],
      ['priority-filter','article.issue','priority'],['confirmation-filter','article.issue','confirmation'],
      ['claim-filter','#evidence tr[data-claim]','claim'],['visual-filter','#evidence tr[data-visual]','visual']];
    for(const [id,selector,key] of filters){
      const actual=await page.locator(selector).evaluateAll((nodes,key)=>[...new Set(nodes.map(n=>n.dataset[key]).filter(Boolean))].sort(),key);
      const offered=await page.locator('#'+id+' option').evaluateAll(nodes=>nodes.map(n=>n.value).filter(Boolean).sort());
      assert.deepEqual(offered,actual,'filter options: '+id);
    }
    for(const link of await page.locator('[data-filter-section]').all()){
      const section=await link.getAttribute('data-filter-section');
      await link.click();
      assert.equal(await page.locator('#section-filter').inputValue(),section);
      const visible=await page.locator('article.issue:visible').evaluateAll(nodes=>nodes.map(n=>n.dataset.section));
      assert.ok(visible.length && visible.every(value=>value===section));
    }
    if(result.issues){
      await page.locator('#reset-issues').click();
      await page.locator('#issue-query').fill('不存在的检索词_no_match_7821');
      assert.equal(await page.locator('article.issue:visible').count(),0);
      assert.ok(await page.locator('#issue-empty').isVisible());
      await shot(page,'empty-state-1440');
      const id=(await page.locator('article.issue').first().getAttribute('id')).slice(6);
      await page.evaluate(id=>{location.hash='#edit-'+id},id);
      await page.locator('#edit-'+id).waitFor({state:'visible'});
      assert.ok(await page.locator('#issue-'+id+' .filter-exception').isVisible());
      await page.locator('#edit-'+id+' a[href="#reading-guide"]').click();
      await page.locator('#reading-guide[open]').waitFor();
      assert.equal(await page.locator('#guide-return').getAttribute('href'),'#edit-'+id);
      await page.locator('#guide-return').click();
      assert.equal(await page.locator('#issue-query').inputValue(),'不存在的检索词_no_match_7821');
      await page.locator('#reset-issues').click();
      await page.evaluate(id=>{location.hash='#issue-'+id},id);
      await shot(page,'issue-1440');
      await page.locator('#issue-'+id+' a[href="#law-'+id+'"]').click();
      await page.locator('#law-'+id+'[open]').waitFor();
      await page.locator('#law-'+id+' summary').click();
      await page.locator('#issue-'+id+' a[href="#law-'+id+'"]').click();
      await page.locator('#law-'+id+'[open]').waitFor();
      for(const card of await page.locator('article.issue').all()){
        const issue=(await card.getAttribute('id')).slice(6);
        const n=await page.locator('#evidence tr[data-related]').evaluateAll((rows,id)=>rows.filter(row=>row.dataset.related.split(' ').includes(id)).length,issue);
        const f=await page.locator('#figures tr[data-related]').evaluateAll((rows,id)=>rows.filter(row=>row.dataset.related.split(' ').includes(id)).length,issue);
        if(n+f){
          const text=`${n} 条权项对照 · ${f} 条附图记录`;
          assert.ok((await card.locator('.related summary').textContent()).includes(text));
          assert.ok((await card.locator('.print-evidence-links').textContent()).includes(text));
          await card.locator('.related summary').click();
          await page.waitForFunction(id=>document.getElementById('related-'+id).dataset.loaded==='true',issue);
          assert.equal(await card.locator('.related tbody tr').count(),n+f);
        }else assert.equal(await card.locator('.related').count(),0);
      }
      // A document loaded directly at a subheading must reveal its legal parent.
      await page.goto(url+'#law-'+id);
      await page.locator('#law-'+id+'[open]').waitFor();
    }
    const hashes=await page.locator('.navigation a').evaluateAll(nodes=>nodes.map(n=>n.hash));
    for(const width of [1440,1100,780,640,560,521,520,390,320]){
      await page.setViewportSize({width,height:844});
      for(const hash of hashes){
        await page.locator('.navigation a[href="'+hash+'"]').click();
        await page.waitForFunction(hash=>Math.abs(document.querySelector(hash).getBoundingClientRect().top-(document.querySelector('.navigation').getBoundingClientRect().height+18))<3 || innerHeight+scrollY>=document.documentElement.scrollHeight-3,hash);
        assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'overflow at '+width);
      }
      result.widths.push(width);
    }
    await page.setViewportSize({width:390,height:844});
    await page.goto(url);
    await shot(page,'overview-390');
    if(result.issues){
      const id=(await page.locator('article.issue').first().getAttribute('id')).slice(6);
      await page.goto(url+'#edit-'+id);
      await shot(page,'edit-390');
    }
    if(await page.locator('#claim-overview').count()){
      await page.locator('a[href="#claim-overview"]').first().click();
      await shot(page,'claims-390');
    }
    await page.setViewportSize({width:1440,height:900});
    await page.goto(url+'#delivery'); await shot(page,'delivery-1440');
    await page.goto(url);
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.className),'skip');
    // beforeprint must be idempotent and restore only panels it opened.
    const before=await page.locator('details').evaluateAll(nodes=>nodes.map(n=>n.open));
    await page.evaluate(()=>{dispatchEvent(new Event('beforeprint'));dispatchEvent(new Event('beforeprint'))});
    assert.equal(await page.locator('details.legal:not([open]), details.review-extra:not([open])').count(),0);
    await page.pdf({path:path.join(destination,'print-check.pdf'),format:'A4',printBackground:true});
    await page.evaluate(()=>dispatchEvent(new Event('afterprint')));
    assert.deepEqual(await page.locator('details').evaluateAll(nodes=>nodes.map(n=>n.open)),before);
    // No-JS has readable body and native details, with filter controls hidden.
    const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
    const fallback=await nojs.newPage(); await fallback.goto(url);
    assert.equal(await fallback.locator('article.issue:visible').count(),result.issues);
    assert.equal(await fallback.locator('.toolbar:visible').count(),0);
    if(await fallback.locator('#claim-overview').count()){
      await fallback.locator('#claim-overview summary').click();
      assert.equal(await fallback.locator('#claim-overview').getAttribute('open'),'');
    }
    await nojs.close();
    assert.deepEqual(result.errors,[]);
    result.passed=true;
    fs.writeFileSync(path.join(destination,'browser-results.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exitCode=1});

