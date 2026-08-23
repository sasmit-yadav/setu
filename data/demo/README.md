# Demo fixtures

## `enrollment-demo.csv`

For the **Register people** screen on the officer console. Upload it, press
**Check the file**, and the dry run reports what would happen without writing
anything — which is what that screen's own copy promises, and what makes it
safe to show live.

The last four rows are deliberately broken so the dry run has something to
reject:

| Row | Why it is rejected |
|---|---|
| `12345,8157,ml` | not a phone number in E.164 |
| `+919000000109,99999999,ml` | `unit_id` 99999999 does not exist |
| `,8157,ml` | no phone |
| `+919000000110,8157,` | no language — falls back to `en` rather than rejecting |

A dry run that only ever says "all good" demonstrates nothing. Eight accepted
and three rejected shows the validation is real.

**Every number in here is in the `+9190000001xx` block and routes nowhere.**
That is on purpose. A CSV of plausible-looking Indian mobile numbers is a
loaded gun: press Save instead of Check and you have enrolled strangers into a
disaster alert system without their consent, and the next Extreme sends them a
warning. Numbers that cannot be dialled cannot do that.

Also note this file lives in `data/demo/`, **not** `data/enrollment/`.
`python run.py import-enrollment` globs `data/enrollment/*.csv` and imports for
real, so a demo fixture sitting there would be one command away from being
loaded on purpose. (That directory is gitignored precisely because what lands
in it is real consented numbers; this file is committed because nothing in it
is.)

### Saving it, if you want to

The dry run returns a `preview_token` and the live import requires it back —
`enrollment.csv_require_dry_run` enforces that you cannot skip the check. If you
do save, remember it changes the numbers on the rest of the demo: **People we
will warn** goes from 5 to 13, and the next Extreme attempts SMS to eight
unroutable lines, which will show up as honest failures on the assurance
ladder. Cancel those rows afterwards, or plan to explain them.
