// Node 22 把目录参数当模块解析：这里转入口，使 `node --test skills/weicoz-govern/tests/` 在新旧版本都能跑。
import('./govern-audit.test.mjs');
