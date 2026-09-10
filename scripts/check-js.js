/** Parse all authored ES modules without executing browser code. */
import {readdirSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
for (const file of readdirSync('assets/js').filter(file => file.endsWith('.js'))) {
  const result = spawnSync(process.execPath, ['--check', `assets/js/${file}`], {stdio: 'inherit'});
  if (result.status !== 0) process.exit(result.status || 1);
}
process.stdout.write('All authored ES modules passed syntax checks.\n');
