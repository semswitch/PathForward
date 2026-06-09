import { makeStyles, tokens } from "@fluentui/react-components";

export const useStyles = makeStyles({
  root: {
    position: "fixed",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    overflowY: "auto",
  },
  page: {
    maxWidth: "1120px",
    marginLeft: "auto",
    marginRight: "auto",
    paddingTop: tokens.spacingVerticalXXL,
    paddingBottom: tokens.spacingVerticalXXL,
    paddingLeft: tokens.spacingHorizontalXXL,
    paddingRight: tokens.spacingHorizontalXXL,
  },
  header: {
    marginBottom: tokens.spacingVerticalXL,
  },
  intro: {
    marginTop: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalM,
  },
  row: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalS,
    rowGap: tokens.spacingVerticalS,
  },
  stack: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalXL,
  },
  // Visually hidden but available to screen readers (aria-live narration).
  srOnly: {
    position: "absolute",
    width: "1px",
    height: "1px",
    paddingTop: "0",
    paddingBottom: "0",
    paddingLeft: "0",
    paddingRight: "0",
    marginTop: "-1px",
    marginBottom: "0",
    marginLeft: "0",
    marginRight: "0",
    overflowX: "hidden",
    overflowY: "hidden",
    clip: "rect(0, 0, 0, 0)",
    whiteSpace: "nowrap",
    borderTopWidth: "0",
    borderBottomWidth: "0",
    borderLeftWidth: "0",
    borderRightWidth: "0",
  },
});
