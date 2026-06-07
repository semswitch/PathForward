import { makeStyles, tokens } from "@fluentui/react-components";

export const useStyles = makeStyles({
  row: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalS,
    rowGap: tokens.spacingVerticalS,
  },
  intro: {
    marginBottom: tokens.spacingVerticalM,
  },
  stem: {
    marginTop: tokens.spacingVerticalS,
    marginBottom: tokens.spacingVerticalS,
  },
});
