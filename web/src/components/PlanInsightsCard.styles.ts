import { makeStyles, tokens } from "@fluentui/react-components";

export const useStyles = makeStyles({
  row: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalS,
    rowGap: tokens.spacingVerticalS,
    marginTop: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalS,
  },
  section: {
    marginTop: tokens.spacingVerticalM,
  },
  narrative: {
    color: tokens.colorNeutralForeground2,
    marginTop: tokens.spacingVerticalS,
  },
  tableWrap: {
    maxHeight: "260px",
    overflowY: "auto",
  },
});
