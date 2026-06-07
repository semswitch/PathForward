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
});
