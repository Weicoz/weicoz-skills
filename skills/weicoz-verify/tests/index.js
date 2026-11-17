// Node 22 把目录参数当模块解析：`node --test skills/weicoz-verify/tests/` 会加载本入口，再转入真实测试。
import('./lib.test.mjs');
