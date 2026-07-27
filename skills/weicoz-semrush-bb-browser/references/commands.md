# Commands

## Keyword Magic

Open live result page:

```bash
bb-browser open "https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordmagic/?q=<query>&db=us&fid=${WEICOZ_SEMRUSH_FID}&__gmitm=<token>"
```

Extract rows from live tab:

```bash
bb-browser site sem3ue/keywordmagic "<query>" us <fid> --json --tab <tab-id>
```

Extract with filters:

```bash
bb-browser site sem3ue/keywordmagic "<query>" us <fid> --minVolume 100 --maxKd 29 --minCpc 0.1 --json --tab <tab-id>
```

## Keyword Overview

Open live result page:

```bash
bb-browser open "https://${WEICOZ_SEMRUSH_PROXY_HOST}/analytics/keywordoverview/?q=<query>&db=us&fid=${WEICOZ_SEMRUSH_FID}&__gmitm=<token>"
```

Extract from live tab:

```bash
bb-browser site sem3ue/keywordoverview "<query>" us <fid> --json --tab <tab-id>
```

## Keyword Manager

Read builder page state:

```bash
bb-browser site sem3ue/keywordmanager --mode builder
```

Build list URL:

```bash
bb-browser site sem3ue/keywordmanager --listId "<listId>" --tab 0 --clusterView 1 --mode url
```
