import java.nio.file.Path;
public final class MigrationDexCases {
 public static void main(String[]args)throws Throwable{
  DexHostVM vm=new DexHostVM(Path.of(args[0]));
  MigrationCases.APPLY=c->vm.call(vm.index("Lshu/wakeup/ShuMigration;->apply(Landroid/content/Context;)V"),new Object[]{c});
  MigrationCases.main(args);
  System.out.println("migration_dex_execution=PASS");
 }
}
