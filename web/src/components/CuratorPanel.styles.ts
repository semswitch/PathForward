import { makeStyles, tokens } from "@fluentui/react-components";

export const useStyles = makeStyles({
  list: {
    display: "flex",
    flexDirection: "column",
    rowGap: tokens.spacingVerticalS,
    marginTop: tokens.spacingVerticalS,
    paddingLeft: "0",
    marginBottom: "0",
    listStyleType: "none",
  },
  item: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalS,
    rowGap: tokens.spacingVerticalXS,
    paddingTop: tokens.spacingVerticalXS,
    paddingBottom: tokens.spacingVerticalXS,
    paddingLeft: tokens.spacingHorizontalS,
    paddingRight: tokens.spacingHorizontalS,
    borderTopLeftRadius: tokens.borderRadiusMedium,
    borderTopRightRadius: tokens.borderRadiusMedium,
    borderBottomLeftRadius: tokens.borderRadiusMedium,
    borderBottomRightRadius: tokens.borderRadiusMedium,
  },
  chosen: {
    backgroundColor: tokens.colorBrandBackground2,
  },
  rank: {
    color: tokens.colorNeutralForeground3,
    minWidth: "1.5em",
  },
  rationale: {
    color: tokens.colorNeutralForeground2,
  },
  row: {
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalS,
    rowGap: tokens.spacingVerticalS,
  },
});
