import { makeStyles, tokens } from "@fluentui/react-components";

export const useStyles = makeStyles({
  meta: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalS,
    rowGap: tokens.spacingVerticalS,
  },
});
