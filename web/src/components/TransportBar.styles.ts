import { makeStyles, tokens } from "@fluentui/react-components";

export const useStyles = makeStyles({
  bar: {
    position: "sticky",
    bottom: 0,
    zIndex: 10,
    display: "flex",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalM,
    rowGap: tokens.spacingVerticalS,
    marginTop: tokens.spacingVerticalXL,
    paddingTop: tokens.spacingVerticalS,
    paddingBottom: tokens.spacingVerticalS,
    paddingLeft: tokens.spacingHorizontalM,
    paddingRight: tokens.spacingHorizontalM,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: tokens.shadow16,
    borderTopLeftRadius: tokens.borderRadiusLarge,
    borderTopRightRadius: tokens.borderRadiusLarge,
  },
  buttons: {
    display: "flex",
    alignItems: "center",
    columnGap: tokens.spacingHorizontalXS,
  },
  caption: {
    flexGrow: 1,
    minWidth: "200px",
    color: tokens.colorNeutralForeground2,
  },
  provenance: {
    marginLeft: "auto",
  },
});
