import DarkModeOutlined from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlined from "@mui/icons-material/LightModeOutlined";
import { Box, Container, IconButton, Stack, Tab, Tabs, Tooltip, Typography } from "@mui/material";
import { useColorScheme } from "@mui/material/styles";
import { useApi } from "./api/client";
import type { Account, IngestRunRow } from "./api/types";
import { LoadingOrError } from "./components/Panel";
import { setAccount } from "./format";
import { useTab } from "./hooks";
import { useResolvedMode } from "./theme";
import { ClosedTrades } from "./views/ClosedTrades";
import { Fx } from "./views/Fx";
import { Ops } from "./views/Ops";
import { Overview } from "./views/Overview";
import { Positions } from "./views/Positions";
import { Statistics } from "./views/Statistics";

const VIEWS = {
  overview: { label: "Overview", view: Overview },
  statistics: { label: "Statistics", view: Statistics },
  fx: { label: "FX", view: Fx },
  positions: { label: "Positions", view: Positions },
  closed: { label: "Closed trades", view: ClosedTrades },
  ops: { label: "Ops", view: Ops },
} as const;
type ViewKey = keyof typeof VIEWS;
const KEYS = Object.keys(VIEWS) as ViewKey[];

function ThemeToggle() {
  const { setMode } = useColorScheme();
  const shown = useResolvedMode();
  const next = shown === "light" ? "dark" : "light";
  return (
    <Tooltip title={`Switch to ${next} mode`}>
      <IconButton aria-label={`Switch to ${next} mode`} onClick={() => setMode(next)} size="small">
        {shown === "light" ? <LightModeOutlined fontSize="small" /> : <DarkModeOutlined fontSize="small" />}
      </IconButton>
    </Tooltip>
  );
}

/** Last ingest at a glance; click through to Ops for the details. */
function LastRun({ onOpen }: { onOpen: () => void }) {
  const { data } = useApi<IngestRunRow[]>("/ops/runs?n=1");
  const run = data?.[0];
  if (!run) return null;
  const ok = run.status === "success";
  return (
    <Tooltip title={ok ? "Last ingest succeeded" : `Last ingest failed: ${run.error_message ?? run.error_code}`}>
      <Typography
        component="button"
        onClick={onOpen}
        variant="body2"
        sx={{ border: 0, background: "none", cursor: "pointer", color: ok ? "text.secondary" : "error.main", p: 0 }}
      >
        <Box component="span" sx={{ color: ok ? "success.main" : "error.main", mr: 0.5 }}>
          {ok ? "●" : "▲"}
        </Box>
        {ok ? `Data to ${run.watermark_after}` : "Last ingest failed"}
      </Typography>
    </Tooltip>
  );
}

export default function App() {
  const [tab, setTab] = useTab(KEYS);
  const View = VIEWS[tab].view;
  const account = useApi<Account>("/account");
  if (account.data) setAccount(account.data); // before the views format any amount
  return (
    <>
      <Box component="header" data-dark sx={{ bgcolor: "background.paper", color: "common.white", borderBottom: 1, borderColor: "divider" }}>
        <Container maxWidth="xl">
          <Stack direction="row" alignItems="center" columnGap={{ xs: 1.5, md: 3 }} sx={{ minHeight: 56 }} flexWrap="wrap">
            <Typography sx={{ fontWeight: 600, letterSpacing: "-0.01em", mr: "auto", "@media (min-width:900px)": { mr: 0 } }}>
              IBKR Portfolio
            </Typography>
            <Tabs
              value={tab}
              onChange={(_, t: ViewKey) => setTab(t)}
              variant="scrollable"
              scrollButtons={false}
              sx={{
                // own row on phones, inline from tablet up
                flex: { xs: "1 1 100%", md: 1 },
                order: { xs: 3, md: 0 },
                minHeight: 48,
                "& .MuiTab-root": { minHeight: 48 },
                "& .MuiTab-root:not(.Mui-selected)": { color: "common.white" },
              }}
            >
              {KEYS.map((k) => (
                <Tab key={k} value={k} label={VIEWS[k].label} disableRipple />
              ))}
            </Tabs>
            <LastRun onOpen={() => setTab("ops")} />
            <ThemeToggle />
          </Stack>
        </Container>
      </Box>
      <Container component="main" maxWidth="xl" sx={{ py: 3 }}>
        {account.data ? <View /> : <LoadingOrError loading={account.isLoading} error={account.error} />}
      </Container>
    </>
  );
}
