import 'package:flutter/material.dart';

class ResponsiveLayout extends StatelessWidget {
  final Widget mobileBody;
  final Widget tabletBody;
  final Widget desktopBody;
  final Widget? largeDesktopBody;

  const ResponsiveLayout({
    super.key,
    required this.mobileBody,
    required this.tabletBody,
    required this.desktopBody,
    this.largeDesktopBody,
  });

  static bool isMobile(BuildContext context) =>
      MediaQuery.sizeOf(context).width < 600;

  static bool isTablet(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= 600 &&
      MediaQuery.sizeOf(context).width < 1024;

  static bool isDesktop(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= 1024 &&
      MediaQuery.sizeOf(context).width < 1440;

  static bool isLargeDesktop(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= 1440;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        if (constraints.maxWidth >= 1440 && largeDesktopBody != null) {
          return largeDesktopBody!;
        } else if (constraints.maxWidth >= 1024) {
          return desktopBody;
        } else if (constraints.maxWidth >= 600) {
          return tabletBody;
        } else {
          return mobileBody;
        }
      },
    );
  }
}
